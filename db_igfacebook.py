
from asyncore import file_dispatcher
import sqlite3
import os
import logging
from ig_gds_utilities import ig_utilities as utilities


class FacebookDB:

    def __init__(self, config):

        """
        Load necesary parameters from send_igfacebook.cfg
        """

        if type(config) == str:

            db_config = utilities.read_parameters(config)
            self.db_file = db_config['facebook_db']['db_file']
            self.db_table_name = db_config['facebook_db']['db_table_name']
        else:

            self.db_file = config.get('facebook_db', 'db_file')
            self.db_table_name = config.get('facebook_db', 'db_table_name')
        self.init_database()

    def connect_database(self):

        """
        Allow connection to database.

        :returns: con
        :rtype: sqlite3 object
        """

        db_dir = os.path.dirname(self.db_file)
        if not os.path.exists(db_dir):
            logging.debug("Creating DB directory")
            os.makedirs(db_dir)

        logging.debug("connecting to BD")
        con = sqlite3.connect(self.db_file)
        con.text_factory = bytes
        logging.debug("connection to DB established")
        return con

    def close_database(self, con):

        """
        Close database conection.

        :param con: sqlite3 database object
        :type con: obj
        """

        con.commit()
        con.close()
        logging.debug("connection to DB closed")

    def init_database(self):

        """
        It checks if the database exists and if it does,
        it creates a table inside the database to store the events.

        :returns: 0
        :returns: -1
        :rtype: int
        """

        logging.info("creating and starting BD")
        try:
            if os.path.isfile(self.db_file):
                return 0
            con = self.connect_database()
            cur = con.cursor()
            sql = """CREATE TABLE %s (
            event_id TEXT , facebook_id TEXT PRIMARY KEY,status TEXT,
            gds_target TEXT)""" % self.db_table_name
            logging.debug("Creating table %s" % self.db_table_name)
            cur.execute(sql)
            self.close_database(con)
            logging.info("Table created")
            return 0
        except sqlite3.Error as e:
            logging.info("Failed to create DB/table: %s" % str(e))
            return -1

    def save_post(self, post_dict):

        """
        It allows to insert a new event in the table inside the database.

        :param post_dict: post dictionary
        :type post_dict: dict
        :returns: 0
        :returns: -1
        :rtype: int
        """

        con = self.connect_database()
        cur = con.cursor()
        sql = """INSERT INTO %s (event_id, facebook_id, status, gds_target )
            VALUES (:event_id,  :facebook_id,
            :status, :gds_target)""" % self.db_table_name

        try:
            cur.execute(sql, post_dict)
            logging.debug("Event '%s' added" % post_dict['event_id'])
            self.close_database(con)
            return 0

        except sqlite3.Error as e:
            logging.debug(
                "Failed to add event %s : %s"
                % (post_dict['event_id'], str(e)))
            return -1

    def dict_factory(self, cursor, row):

        """
        Convert a row of a database to a dictionary using a query.

        :param cursor: element that will represent a set of data determined by a query
        :param row: database row
        :type token_dict: dict
        :returns: d
        :rtype: dictionary
        """

        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def get_post(self, select="*", where=None):

        """
        It makes a call to ``send_igfacebook`` and checks if an event has already been
        posted previously by querying the database using the id to compare,
        finally it returns a list of events.

        :param select="*": query instruction to select all elements
        :type select="*": str
        :param where=None: query condition
        :type where=None: null
        :returns: events
        :rtype: list
        """

        con = self.connect_database()
        con.row_factory = self.dict_factory
        con.text_factory = str
        cur = con.cursor()
        sql = "SELECT %s FROM %s " % (select, self.db_table_name)
        if where:
            sql += "WHERE %s " % where
        cur.execute(sql)
        events = cur.fetchall()
        self.close_database(con)
        return events

    def delete_post(self, event_id):
        con = self.connect_database()
        cur = con.cursor()
        sql = "DELETE FROM %s WHERE event_id='%s'" % (self.db_table_name, event_id)
        try:
            cur.execute(sql)
            con.commit()
            return True
        except sqlite3.Error as e:
            return str(e)

    def update_post(self, post_dict, column, value):
        # post_dict["table"] = configFaceTweet.tw_dbtable
        con = self.connect_database()
        cur = con.cursor()
        sql = """UPDATE %s SET %s = %s WHERE event_id= '%s'
        """ % (self.db_table_name, column, value, post_dict['event_id'])
        try:
            logging.info("SQL: %s" % sql)
            cur.execute(sql, post_dict)
            logging.info("Event %s inserting")
            self.close_database(con)
            return 0
        except sqlite3.Error as e:
            logging.error("Failed to insert value: %s. Error:  %s" % (value, str(e)))
            return -1
