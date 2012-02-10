# -*- test-case-name: magriculture.workers.tests.test_lactation -*-

import json
import re

from twisted.python import log
from twisted.python.log import logging
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application import ApplicationWorker
from vumi.session import getVumiSession, delVumiSession, TraversedDecisionTree
from vumi.workers.session.worker import SessionConsumer, SessionPublisher, SessionWorker
from vumi.message import Message
from vumi.tests.utils import FakeRedis
#from vumi.webapp.api import utils
import vumi.options


class MenuConsumer(SessionConsumer):
    queue_name = "xmpp.inbound.gtalk.vumi@praekeltfoundation.org"
    routing_key = "xmpp.inbound.gtalk.vumi@praekeltfoundation.org"
    test_yaml = '''
    __data__:
        url: 173.45.90.19/dis-uat/api/getFarmerDetails
        username: admin
        password: Admin1234
        params:
            - telNo
        json: >

    __start__:
        display:
            english: "Hello."
        next: farmers

    farmers:
        question:
            english: "Hi. There are multiple farmers with this phone number. Who are you?"
        options: name
        next: cows

    cows:
        question:
            english: "For which cow would you like to submit a milk collection?"
        options: name
        next: quantityMilked

    quantityMilked:
        question:
            english: "How much milk was collected?"
        validate: integer
        next: quantitySold

    quantitySold:
        question:
            english: "How much milk did you sell?"
        validate: integer
        next: milkTimestamp

    milkTimestamp:
        question:
            english: "When was this collection done?"
        options:
              - display:
                    english: "Today"
                default: today
                next: __finish__
              - display:
                    english: "Yesterday"
                default: yesterday
                next: __finish__
              - display:
                    english: "An earlier day"
                next:
                    question:
                        english: "Which day was it [dd/mm/yyyy]?"
                    validate: date
                    next: __finish__

    __finish__:
        display:
            english: "Thank you! Your milk collection was registered successfully."

    __post__:
        url: 173.45.90.19/dis-uat/api/addMilkCollections
        username: admin
        password: Admin1234
        params:
            - result
    '''


    def consume_message(self, message):
        response = ''
        if not self.yaml_template:
            self.set_yaml_template(self.test_yaml)
        recipient = message.payload['sender']
        sess = self.get_session(recipient)
        if not sess.get_decision_tree().is_started():
            sess.get_decision_tree().start()
            response += sess.get_decision_tree().question()
        else:
            sess.get_decision_tree().answer(message.payload['message'])
            if not sess.get_decision_tree().is_completed():
                response += sess.get_decision_tree().question()
            response += sess.get_decision_tree().finish() or ''
            if sess.get_decision_tree().is_completed():
                sess.delete()
        sess.save()
        self.publisher.publish_message(Message(recipient=recipient, message=response))


    def call_for_json(self, MSISDN):
        MSISDN = "456789"
        if self.data_url['url']:
            params = [(self.data_url['params'][0], str(MSISDN))]
            url = self.data_url['url']
            auth_string = ''
            if self.data_url['username']:
                auth_string += self.data_url['username']
                if self.data_url['password']:
                    auth_string += ":" + self.data_url['password']
                auth_string += "@"
            resp_url, resp = utils.callback("http://"+auth_string+url, params)
            return resp
        return None


class MenuPublisher(SessionPublisher):
    routing_key = "xmpp.outbound.gtalk.vumi@praekeltfoundation.org"


class MenuWorker(SessionWorker):
    @inlineCallbacks
    def startWorker(self):
        log.msg("Starting the MenuWorker")
        log.msg("vumi.options: %s" % (vumi.options.get()))
        self.publisher = yield self.start_publisher(MenuPublisher)
        yield self.start_consumer(MenuConsumer, self.publisher)

    def stopWorker(self):
        log.msg("Stopping the MenuWorker")



class CellulantMenuConsumer(MenuConsumer):
    queue_name = "ussd.inbound.cellulant.http"
    routing_key = "ussd.inbound.cellulant.http"

    def unpackMessage(self, message):
        mess = message.payload['message']
        try:
            if len(mess.get('content', '')) > 0:
                ussd_ = re.search(
                      '^(?P<SESSIONID>[^|]*)'
                    +'\|(?P<NETWORKID>[^|]*)'
                    +'\|(?P<MSISDN>[^|]*)'
                    +'\|(?P<MESSAGE>[^|]*)'
                    +'\|(?P<OPERATION>[^|]*)$',
                    mess['content'])
                if ussd_:
                    ussd = ussd_.groupdict()
                    ussd['api'] = '2.1'
                    return ussd
        except Exception, e:
            log.err(e)
        #'CURRENTLEVEL': ['239'],
        #'SESSIONFILE': ['/var/www/ussdSessions/16539634_254717201184_2011_Jun_Tue_120711'],
        #'EXTRA': ['null'],
        #'MSISDN': ['254717201184'],
        #'sessionID': ['110607120709000'],
        #'ABORT': ['0'],
        #'opCode': ['BEG'],
        #'TEMPLEVEL': ['1'],
        #'INPUT': ['8864']}
        try:
            mess = mess.get('args', {})
        except:
            mess = {}
        ussd = {}
        ussd['CURRENTLEVEL'] = mess.get('CURRENTLEVEL', ['null']).pop()
        ussd['SESSIONFILE'] = mess.get('SESSIONFILE', ['null']).pop()
        ussd['MSISDN'] = mess.get('MSISDN', ['null']).pop()
        ussd['EXTRA'] = mess.get('EXTRA', ['null']).pop()
        ussd['SESSIONID'] = mess.get('sessionID', ['null']).pop()
        ussd['ABORT'] = mess.get('ABORT', ['null']).pop()
        ussd['OPERATION'] = mess.get('opCode', ['null']).pop()
        ussd['TEMPLEVEL'] = mess.get('TEMPLEVEL', ['null']).pop()
        ussd['MESSAGE'] = str(mess.get('INPUT', ['null']).pop())
        ussd['api'] = '1.0'
        return ussd

    def packMessage_1_0(self,
            SESSIONID = None,
            NETWORKID = None,
            MSISDN = None,
            MESSAGE = None,
            OPERATION = None,
            **kwargs):
        nextLevel = '1'
        message = MESSAGE
        valueOfSelection = 'null'
        serviceID = 'null'
        status = 'null'
        if OPERATION == "END":
            status = 'end'
        extra = 'null'
        return "%s|%s|%s|%s|%s|%s" % (
                nextLevel,
                message,
                valueOfSelection,
                serviceID,
                status,
                extra)

    def packMessage_2_1(self,
            SESSIONID,
            NETWORKID,
            MSISDN,
            MESSAGE,
            OPERATION,
            **kwargs):
        return "%s|%s|%s|%s|%s" % (
                SESSIONID,
                NETWORKID,
                MSISDN,
                MESSAGE,
                OPERATION)


    def consume_message(self, message):
        log.msg("Message: %s" % (message))
        ussd = self.unpackMessage(message)
        log.msg("USSD: %s" % (ussd))
        response = ''
        if True:
            if not self.yaml_template:
                self.set_yaml_template(self.test_yaml)
            sess = self.get_session(ussd['SESSIONID'])
            if not sess.get_decision_tree().is_started():
                sess.get_decision_tree().start()
                response += sess.get_decision_tree().question()
                ussd['OPERATION'] = 'INV'
            else:
                sess.get_decision_tree().answer(ussd['MESSAGE'])
                if not sess.get_decision_tree().is_completed():
                    response += sess.get_decision_tree().question()
                    ussd['OPERATION'] = 'INV'
                response += sess.get_decision_tree().finish() or ''
                if sess.get_decision_tree().is_completed():
                    sess.delete()
                    ussd['OPERATION'] = 'END'
            sess.save()
        ussd['MESSAGE'] = response
        #ussd['MESSAGE'] = "\\n".join(response.split("\n"))
        log.msg("ussd: %s" % ussd)
        if ussd['api'] == '2.1':
            packed_message = self.packMessage_2_1(**ussd)
        else:
            packed_message = self.packMessage_1_0(**ussd)
        self.publisher.publish_message(Message(
                uuid=message.payload['uuid'],
                message=packed_message),
            routing_key = message.payload['return_path'].pop())


class CellulantMenuWorker(SessionWorker):
    @inlineCallbacks
    def startWorker(self):
        log.msg("Starting the CellulantMenuWorker")
        log.msg("vumi.options: %s" % (vumi.options.get()))
        self.publisher = yield self.start_publisher(SessionPublisher)
        yield self.start_consumer(CellulantMenuConsumer, self.publisher)

    def stopWorker(self):
        log.msg("Stopping the MenuWorker")


class MMMobileMenuConsumer(MenuConsumer):
    queue_name = "ussd.inbound.mmmobile.http"
    routing_key = "ussd.inbound.mmmobile.http"

    def consume_message(self, message):
        log.msg("Message: %s" % (message))
        self.publisher.publish_message(Message(
                uuid=message.payload['uuid'],
                message='CON if you keep replying, you should get this response each time.'),
            routing_key = message.payload['return_path'].pop())

class MMMobileMenuWorker(SessionWorker):
    @inlineCallbacks
    def startWorker(self):
        log.msg("Starting the MMMobileMenuWorker")
        log.msg("vumi.options: %s" % (vumi.options.get()))
        self.publisher = yield self.start_publisher(SessionPublisher)
        yield self.start_consumer(MMMobileMenuConsumer, self.publisher)

    def stopWorker(self):
        log.msg("Stopping the MenuWorker")


class SessionApplicationWorker(ApplicationWorker):

    def set_yaml_template(self, yaml_template):
        self.yaml_template = yaml_template

    def set_data_url(self, data_source):
        self.data_url = data_source

    def set_post_url(self, post_source):
        self.post_url = post_source

    def post_result(self, result):
        # TODO need actual post but
        # just need this to override in testing for now
        #print self.post_url
        #print result
        pass

    def call_for_json(self):
        # TODO need actual retrieval but
        # just need this to override in testing for now
        return '{}'

    def consume_message(self, message):
        # TODO: Eep! This code is broken!
        log.msg("session message %s consumed by %s" % (
            json.dumps(dictionary), self.__class__.__name__))
        #dictionary = message.get('short_message')

    def get_session(self, MSISDN):
        #sess = getVumiSession(self.r_server,
                              #self.routing_key + '.' + MSISDN)
        sess = getVumiSession(self.r_server,
                self.transport_name + '.' + MSISDN)
        if not sess.get_decision_tree():
            sess.set_decision_tree(self.setup_new_decision_tree(MSISDN))
        return sess

    def del_session(self, MSISDN):
        return delVumiSession(self.r_server, MSISDN)

    def setup_new_decision_tree(self, MSISDN, **kwargs):
        decision_tree = TraversedDecisionTree()
        yaml_template = self.yaml_template
        decision_tree.load_yaml_template(yaml_template)
        self.set_data_url(decision_tree.get_data_source())
        self.set_post_url(decision_tree.get_post_source())
        if self.data_url.get('url'):
            json_string = self.call_for_json()
            decision_tree.load_json_data(json_string)
        else:
            decision_tree.load_dummy_data()
        return decision_tree


class LactationWorker(SessionApplicationWorker):
    """A worker that presents a USSD menu allowing farmers to
    record cows milk production.

    Configuration parameters:

    :type transport_name: str
    :param transport_name:
        Name of the transport (or dispatcher) to receive messages from and
        send message to.
    :type worker_name: str
    :param worker_name:
        Name of the worker. Used as the redis key prefix.
    """

    MAX_SESSION_LENGTH = 5 * 60

    test_yaml = '''
    __data__:
        url: 173.45.90.19/dis-uat/api/getFarmerDetails
        username: admin
        password: Admin1234
        params:
            - telNo
        json: "{}"

    __start__:
        display:
            english: "Hello."
        next: farmers

    farmers:
        question:
            english: "Hi. There are multiple farmers with this phone number. Who are you?"
        options: name
        next: cows

    cows:
        question:
            english: "For which cow would you like to submit a milk collection?"
        options: name
        next: quantityMilked

    quantityMilked:
        question:
            english: "How much milk was collected?"
        validate: integer
        next: quantitySold

    quantitySold:
        question:
            english: "How much milk did you sell?"
        validate: integer
        next: milkTimestamp

    milkTimestamp:
        question:
            english: "When was this collection done?"
        options:
              - display:
                    english: "Today"
                default: today
                next: __finish__
              - display:
                    english: "Yesterday"
                default: yesterday
                next: __finish__
              - display:
                    english: "An earlier day"
                next:
                    question:
                        english: "Which day was it [dd/mm/yyyy]?"
                    validate: date
                    next: __finish__

    __finish__:
        display:
            english: "Thank you! Your milk collection was registered successfully."

    __post__:
        url: 173.45.90.19/dis-uat/api/addMilkCollections
        username: admin
        password: Admin1234
        params:
            - result
    '''

    @inlineCallbacks
    def startWorker(self):
        self.worker_name = self.config['worker_name']
        #self.set_yaml_template(self.test_yaml)
        self.yaml_template = None
        self.r_server = FakeRedis()
        yield super(LactationWorker, self).startWorker()

    @inlineCallbacks
    def stopWorker(self):
        yield super(LactationWorker, self).stopWorker()

    @inlineCallbacks
    def consume_user_message(self, msg):
        #print dir(msg)
        #print msg
        try:
            response = ''
            continue_session = False
            if True:
                if not self.yaml_template:
                    self.set_yaml_template(self.test_yaml)
                sess = self.get_session(msg.user())
                if not sess.get_decision_tree().is_started():
                    # TODO check this corresponds to session_event = new
                    sess.get_decision_tree().start()
                    response += sess.get_decision_tree().question()
                    continue_session = True
                else:
                    # TODO check this corresponds to session_event = resume
                    sess.get_decision_tree().answer(msg.payload['content'])
                    if not sess.get_decision_tree().is_completed():
                        response += sess.get_decision_tree().question()
                        continue_session = True
                    response += sess.get_decision_tree().finish() or ''
                    if sess.get_decision_tree().is_completed():
                        self.post_result(json.dumps(
                            sess.get_decision_tree().get_data()))
                        sess.delete()
                sess.save()
        except Exception, e:
            print e
        user_id = msg.user()
        self.reply_to(msg, response, continue_session)
        yield None
