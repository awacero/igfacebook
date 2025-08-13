#!/usr/bin/env seiscomp-python

from datetime import datetime, timedelta
import sys
import os
import json

sys.path.append(os.path.join(os.environ['SEISCOMP_ROOT'], 'share/gds/tools/'))
###
# This import is located here due to local libraries that
# CAN NOT be appended to PYTHONPATH due to name repetition
###
from lib import bulletin, spooler

import paho.mqtt.client as mqtt
import logging
import logging.config

logging_file = os.path.join(
    os.environ['SEISCOMP_ROOT'], 'var/log/', 'gds_service_igfacebook.log')
logging.config.dictConfig({'version': 1, 'disable_existing_loggers': True})
logging.basicConfig(filename=logging_file, format='%(asctime)s %(message)s')
logger = logging.getLogger("igfacebook")
logger.setLevel(logging.DEBUG)


class MQTTConfig:

    def __init__(self, config):
        """Load MQTT config parameters"""
        prefix = "mqtt"
        try:
            self.host = config.get(prefix, "host")
            self.port = int(config.get(prefix, "port"))
            self.topic = config.get(prefix, "topic")
            self.username = config.get(prefix, "username")
            self.password = config.get(prefix, "password")
            self.hour_limit = int(config.get(prefix, "hour_limit"))
        except Exception as e:
            logger.error("##Error reading mqtt config file: %s" % str(e))


class SpoolSendMQTT(spooler.Spooler):

    def __init__(self):
        """Load ``send_igmqtt`` config"""
        spooler.Spooler.__init__(self)
        self.mqtt_config = MQTTConfig(self._config)
        logger.info(
            "##Configuration loaded: %s" % self.mqtt_config.hour_limit)

    def spool(self, addresses, content):
        """Publish an event through MQTT"""
        logger.info(
            "##Start spool() for SpoolSendMQTT with: %s" % (addresses))

        try:
            bulletin_object = bulletin.Bulletin()
            bulletin_object.read(content)
        except Exception as e:
            raise Exception("Error starting spool(): %s" % str(e))

        logger.debug(
            "Event info to publish: %s" % (bulletin_object.plain))
        event_info = bulletin_object.plain.split(" ")
        event_id = event_info[1].split(":")[1]
        event_status = event_info[2]
        event_datetime = datetime.strptime(
            "%s %s" % (event_info[3], event_info[4]),
            "%Y-%m-%d %H:%M:%S")

        event_dict = {'text': '%s' % bulletin_object.plain}

        logger.info("event info: %s %s %s",
                    event_id, event_status, event_datetime)

        if not self.check_antiquity(event_datetime):
            logger.info("event too old. Limit is %s hours",
                        self.mqtt_config.hour_limit)
            return True

        try:
            client = self.connect_mqtt()
            result = self.publish_event(client, event_dict)
            client.disconnect()
            return result
        except Exception as e:
            logger.error("Error in spool: %s" % str(e))
            raise Exception("Error in spool: %s" % str(e))

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            client = mqtt.Client()
            if self.mqtt_config.username:
                client.username_pw_set(self.mqtt_config.username,
                                       self.mqtt_config.password)
            client.connect(self.mqtt_config.host, self.mqtt_config.port)
            return client
        except Exception as e:
            logger.error("Error trying to connect mqtt: %s" % str(e))
            raise Exception("Error trying to connect mqtt: %s" % str(e))

    def publish_event(self, client, event_dict):
        """Publish event_dict as JSON"""
        logger.info("info to publish: %s" % event_dict)
        try:
            payload = json.dumps(event_dict)
            result = client.publish(self.mqtt_config.topic, payload)
            result.wait_for_publish()
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error("Error trying to publish to MQTT: %s" % str(e))
            return False

    def check_antiquity(self, limit_date_time):
        """Checks the age of an event"""
        date_check = datetime.now() - timedelta(hours=self.mqtt_config.hour_limit)
        if date_check < limit_date_time:
            return True
        else:
            return False


if __name__ == "__main__":
    app = SpoolSendMQTT()
    app()

