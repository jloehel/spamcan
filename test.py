import nose
import unittest
import os
import shutil
import threading
import socket
import time
import tempfile
import json

import database

from testing import pop_server
from modules import mail_util


class SpamCanDBTest(unittest.TestCase):

    def setUp(self):
        paths = ["data-test/", "data-test/files"]
        for path in paths:
            if not os.path.exists(path):
                os.makedirs(path)
        configs = ["conf/accounts.json", "conf/spamcan.json"]
        for conf in configs:
            if not os.path.exists(conf):
                shutil.copyfile(conf + ".dist", conf + ".test")

    def tearDown(self):
        os.unlink("data-test/spamcan.db.test")
        shutil.rmtree("data-test")
        configs = ["conf/accounts.json.test", "conf/spamcan.json.test"]
        for conf in configs:
            if os.path.exists(conf):
                os.unlink(conf)

    def test_database(self):
        self.db = database.Database(db_test="sqlite:///data-test/spamcan.db.test")
        accounts = self.db.fetch_all()
        self.assert_(len([acc for acc in accounts]) == 1)


class SpamCanPOPTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        paths = ["data/", ]
        for path in paths:
            if not os.path.exists(path):
                os.makedirs(path)
        configs = ["conf/accounts.json", "conf/spamcan.json"]
        for conf in configs:
            if not os.path.exists(conf):
                shutil.copyfile(conf + ".dist", conf)
        cls.server = pop_server.pop_server()
        cls.server_port = cls.server.server_address[1]
        cls.t = threading.Thread(target=cls.server.serve_forever)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.socket.close()
        cls.t.join()

    def test_pop_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("localhost", SpamCanPOPTest.server_port))
            received = sock.recv(1024)
            sock.sendall("QUIT foobar" + "\n")
        finally:
            sock.close()
        self.assert_(received == "+OK SpamCan test server ready" + "\r\n")

    def test_pop_client(self):
        account_config = {
                          "user_name": "foo@localhost",
                          "password": "foobar",
                          "protocol": "pop3",
                          "hostname": "localhost:{0}".format(SpamCanPOPTest.server_port),
                          "smtp_host": "localhost"
                          }
        account = database.Account(account_config)
        mail_handler = mail_util.MailUtil()
        protocol_handler = mail_handler.request(account)
        count = protocol_handler.get_stats()
        protocol_handler.disconnect()
        self.assert_(count == 1)

    def test_get_stats_method(self):

        tmpdir = tempfile.mkdtemp()
        try:
            self.write_config_files(tmpdir)
            mail_handler = mail_util.MailUtil()
            db = database.Database(conf_dir=tmpdir)
            account = db.fetch_by_id(1)
            protocol_handler = mail_handler.request(account)
            if protocol_handler:
                account.remote_count = protocol_handler.get_stats()
                protocol_handler.disconnect()
            self.assert_(account.remote_count == 1)
        finally:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir)

    def write_config_files(self, tmpdir):
        account_config = {
            "user_name": "user@example.com",
            "password": "p4ssw0rD",
            "protocol": "pop3",
            "hostname": "127.0.0.1:{0}".format(SpamCanPOPTest.server_port),
            "smtp_host": "smtp.example.com"}

        spamcan_config = {"database": "sqlite:///{0}".format(os.path.join(tmpdir, "spamcan.db"))}

        with open(os.path.join(tmpdir, "accounts.json"), "w") as f:
            json.dump(account_config, f)
        with open(os.path.join(tmpdir, "spamcan.json"), "w") as f:
            json.dump(spamcan_config, f)


if __name__ == "__main__":
    nose_conf = nose.config.Config()
    nose_conf.verbosity = 3
    nose.main(config=nose_conf)
