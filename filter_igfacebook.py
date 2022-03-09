#!/usr/bin/env seiscomp-python

import sys,os

sys.path.append( os.path.join(os.environ['SEISCOMP_ROOT'],'share/gds/tools/')) 

import seiscomp3.Core
import seiscomp3.DataModel
from lib import bulletin
from lib.filter import Filter

import pytz
from datetime import datetime
from ig_gds_utilities import ig_utilities as utilities 

import logging
import logging.config


logging_file = os.path.join(os.environ['SEISCOMP_ROOT'],'var/log/','gds_service_igfacebook.log')
logging.basicConfig(filename=logging_file, format='%(asctime)s %(message)s')
logger = logging.getLogger("igfacebook")
logger.setLevel(logging.DEBUG)


class FacebookFilterConfig():
    
    def __init__(self):
        self.config = utilities.read_parameters(utilities.config_path)



class FacebookFilter(Filter):

    def filter(self,event_parameter):

        fb_cfg = utilities.read_parameters(utilities.config_path)
        
        logger.info("start igFacebookFilter")
        try:
            event = self.parseEventParameters(event_parameter)
            event_bulletin = bulletin.Bulletin()
            event_bulletin.plain = "#SISMO ID:{id} {status} {time_local} TL Magnitud: {magVal}" \
                            " Profundidad: {depth} km, {nearest_city}, Latitud: {lat} Longitud:{lon}." \
                            " {event_country} Sintió este sismo (débil, fuerte, muy fuerte)? Cuéntenos en dónde? Repórtelo en {survey_url} ".format(**event)
            logger.info("Create map if it does not exist yet")

            event_image_path = "{0}/{id}/{id}-map.png".format(fb_cfg['ig_info']['eqevent_page_path'],**event)          
            event_path = "{0}/{id}/".format(fb_cfg['ig_info']['eqevent_page_path'],**event)
            event_info = {'event_id':event['id']}

            if not os.path.isfile(event_image_path):
                logger.info("create map ")
                if not os.path.exists(event_path):
                    os.makedirs(event_path)
                map_result = utilities.generate_google_map(event['lat'],event['lon'],event_info)

                if map_result == False:
                    map_result = utilities.generate_gis_map(event['lat'],event['lon'],event_info)
            
            return event_bulletin

        except Exception as e:
            logger.error("Error in igFacebookFilter was: %s" %str(e))
            return None
        



    def parseEventParameters(self,event_parameter):

        event={}
        event["id"]     = ""
        event["region"] = ""
        event["magVal"] = ""
        event["time"]   = ""
        event["lat"]    = ""
        event["lon"]    = ""
        event["depth"]  = ""
        event["status"]   = ""
        event["type"] = ""
        event["nearest_city"] = ""
        event["time_local"] = ""
        event['survey_url'] = ""

        if event_parameter.eventCount()>1:
            logger.info("More than one event. Return empty dictionary")
            return event

        event_object = event_parameter.event(0)
        event["id"] = event_object.publicID()

        for j in range(0,event_object.eventDescriptionCount()):
            ed = event_object.eventDescription(j)
            if ed.type() == seiscomp3.DataModel.REGION_NAME:
                event["region"] = ed.text()
                break

        magnitude = seiscomp3.DataModel.Magnitude.Find(event_object.preferredMagnitudeID())
        if magnitude:
            event['magVal'] = "%0.1f" %magnitude.magnitude().value()

        origin = seiscomp3.DataModel.Origin.Find(event_object.preferredOriginID())
        if origin:
            event["time"] = origin.time().value().toString("%Y-%m-%d %T")
            event["time_local"] = self.get_local_datetime(event["time"]).strftime('%Y-%m-%d %H:%M:%S')
            event["lat"]  = "%.2f" % origin.latitude().value() 
            event["lon"]  = "%.2f" % origin.longitude().value()

            try: 
                event["depth"] = "%.0f" % origin.depth().value()
            except seiscomp3.Core.ValueException: 
                pass
            try: 
                event["status"]  = "%s" %seiscomp3.DataModel.EEvaluationModeNames.name(event_parameter.origin(0).evaluationMode())
            except: 
                event["status"] = "automatic"
            try:
                typeDescription = event_object.type()
                event["type"] = "%s" %seiscomp3.DataModel.EEventTypeNames.name(typeDescription)
            except: 
                event["type"] = "NOT SET"
            
            event["nearest_city"] = utilities.get_closest_city(origin.latitude().value(),origin.longitude().value())
            event["survey_url"] = str(utilities.get_survey_url(self.get_local_datetime(event['time']),event['id']))
            event["event_country"] = utilities.get_message_by_country(origin.latitude().value(),origin.longitude().value())
            event["status"] = self.status(event["status"])
        return event


    def status(self,stat):
        if stat == 'automatic':
            stat = 'Preliminar'
        elif stat == 'manual':
            stat = 'Revisado'
        else:
            stat = '-'
        return stat

    def get_local_datetime(self,datetime_utc_str):
        ##REPLACE BY A CONFIG PARAMETER 
        
        local_zone=pytz.timezone('America/Guayaquil')
        datetime_UTC=datetime.strptime(datetime_utc_str,'%Y-%m-%d %H:%M:%S')
        datetime_EC=datetime_UTC.replace(tzinfo=pytz.utc).astimezone(local_zone)
        return datetime_EC

if __name__ == "__main__":
    app = FacebookFilter()
    sys.exit(app())