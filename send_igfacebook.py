#!/usr/bin/env seiscomp-python

from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.environ['SEISCOMP_ROOT'], 'share/gds/tools/'))

from lib import bulletin, spooler

import facebook
from ig_gds_utilities import ig_utilities as utilities
from db_igfacebook import FacebookDB
import logging
import logging.config

logging_file = os.path.join(
    os.environ['SEISCOMP_ROOT'], 'var/log/', 'gds_service_igfacebook.log')
logging.config.dictConfig({'version': 1, 'disable_existing_loggers': True})
logging.basicConfig(filename=logging_file, format='%(asctime)s %(message)s')
logger = logging.getLogger("igfacebook")
logger.setLevel(logging.DEBUG)


class FacebookConfig:

    def __init__(self, config):
        """
        Load Facebook config parameters

        :param self FacebookConfig: Configuration object
        :returns: configuration loader
        """
        prefix = "facebook"
        try:
            self.accounts_file = config.get(prefix, "accounts_file")
            self.hour_limit = int(config.get(prefix, "hour_limit"))
            self.eqevent_path = config.get(prefix, "eqevent_path")
        except Exception as e:
            logger.error("##Error reading facebook config file: %s" % str(e))

        prefix = "facebook_db"
        try:
            self.db_file = config.get(prefix, "db_file")
            self.db_table_name = config.get(prefix, "db_table_name")
        except Exception as e:
            logger.error(
                "##Error reading facebook db config file: %s" % str(e))


class SpoolSendFacebook(spooler.Spooler):

    def __init__(self):
        """
        Load ``send_igFacebook`` config and read twitter account info,
        also create FacebookDB object

        :param self SpoolSendFacebook: 
        :returns: None
        """

        spooler.Spooler.__init__(self)
        self.facebook_config = FacebookConfig(self._config)
        logger.info(
            "##Configuration loaded: %s" % self.facebook_config.hour_limit)
        try:
            self.facebook_accounts = utilities.read_config_file(
                self.facebook_config.accounts_file)
        except Exception as e:
            logger.info("Error reading facebook_accounts file: %s" % str(e))

        try:
            logger.info(
                "Create db object. It will initialize the db if there is none")
            self.facebook_db = FacebookDB(self._config)
            logger.info("## fb_db object created:%s" % self.facebook_db)
        except Exception as e:
            logger.error("Error creating facebookDB object: %s" % str(e))

    def spool(self, addresses, content):
        """
        Take an addresses list and check against the DB if the event has been published
        alredy, also read the content element with a ``bulletin object`` to extract info
        about the event

        :param addresses: list.
        :type addresses: list[str]
        :param content: 
        :returns: True
        :returns: False
        :rtype: boolean
        """
        logger.info(
            "##Start spool() for SpoolSendFacebook with: %s" % (addresses))

        try:
            bulletin_object = bulletin.Bulletin()
            bulletin_object.read(content)
        except Exception as e:
            raise Exception("Error starting spool(): %s" % str(e))

        logger.debug(
            "Event info to facebook post: %s" % (bulletin_object.plain))
        event_info = bulletin_object.plain
        event_info = event_info.split(" ")
        event_id = event_info[1].split(":")[1]
        event_status = event_info[2]
        event_datetime = datetime.strptime(
                         "%s %s" % (event_info[3], event_info[4]),
                         "%Y-%m-%d %H:%M:%S")

        # The filter is in charge of create a JPG image in
        # case eqevents is not ready.

        event_image_path = "%s/%s/%s-map.png" % (
                           self.facebook_config.eqevent_path,
                           event_id, event_id)

        if not os.path.isfile(event_image_path):
            event_image_path = "%s/%s/%s-map.jpg"\
                               % (self.facebook_config.eqevent_path,
                                  event_id, event_id)

        event_dict = {'text': '%s' % bulletin_object.plain,
                      'image_path': event_image_path}

        logger.info("event info to look in db: %s %s %s"
                    % (event_id, event_status, event_datetime))

        """Check if the event is within the hour_limit """
        if not self.check_antiquity(event_datetime):
            logger.info("event too old. Limit is %s hours"
                        % self.facebook_config.hour_limit)
            return True

        for address in addresses:
            """Check against the DB if the event has been published already"""
            select = "*"
            where = "event_id='%s' AND status='%s' AND gds_target='%s'"\
                    % (event_id, event_status, address[1])
            rows = self.facebook_db.get_post(select, where)

            logger.info("event checked in db: %s" % where)
            if len(rows) == 1:
                logger.info("Event already published. Exit")
                return True

            logger.info("Event not found. Continue to publish")

            try:
                """Create the api to facebook"""

                logger.info("Start facebook publication")
                facebook_account = self.facebook_accounts[address[1]]
                logger.info(facebook_account)
                facebook_api = self.connect_facebook(facebook_account)
                facebook_id = self.post_event(facebook_api, event_dict)

                if facebook_id == False:
                    logger.error("Error posting to facebook")
                    return False
                else:
                    logger.info("Insert facebook_id into DB :%s" % facebook_id)
                    event_row = {'event_id': event_id,
                                 'facebook_id': facebook_id['post_id'],
                                 'status': event_status,
                                 'gds_target': address[1]}

                    if self.facebook_db.save_post(event_row) == 0:
                        logger.info("Post info inserted into DB: %s" %
                                    event_row)
                        return True
                    else:
                        logger.info("Failed to insert facebook info into DB")
                        return False

            except Exception as e:

                logger.error("Error in spool: %s" % str(e))
                raise Exception("Error in spool: %s" % str(e))

    def connect_facebook(self, token_dict):
        """
        Takes a ``token_dict`` which is a dictionary of tokens and
        is then used to authenticate to Facebook Api

        :param token_dict: token dictionary
        :type token_dict: dict
        :returns: facebook_api
        """

        try:
            facebook_api = facebook.GraphAPI(token_dict['token'])
            return facebook_api
        except Exception as e:
            logger.error("Error trying to connect facebook: %s" % str(e))
            raise Exception("Error trying to connect facebook: %s" % str(e))

    def post_event(self, facebook_api, event_dict):

        """
        Takes a ``facebook_api`` object to use api facebook and then publish a post with info of
        event_dict.

        :param facebook_api: object that contains credentials of authentication for the Api twitter
        :type facebook_api: obj
        :param event_dict: event dictionary
        :type event_dict: dict
        :returns: post_id
        :rtype: int
        """

        logger.info("info to post: %s" % event_dict)
        try:
            post_id = facebook_api.put_photo(image=open(
                event_dict['image_path'], 'rb'), message=event_dict['text'])
            return post_id
        except Exception as e:
            logger.error("Error trying to post to Facebook: %s" % str(e))
            return False

    def check_antiquity(self, limit_date_time):

        """
        Checks the age of an event and validates it with ``limit_date_time``.

        :param limit_date_time: datetime object
        :type limit_date_time: obj
        :returns: True
        :returns: False
        :rtype: boolean
        """

        date_check = datetime.now()
        - timedelta(hours=self.facebook_config.hour_limit)

        if date_check < limit_date_time:
            return True
        else:
            return False


if __name__ == "__main__":
    app = SpoolSendFacebook()
    app()
