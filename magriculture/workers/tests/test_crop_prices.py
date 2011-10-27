"""Tests for magriculture.workers.crop_prices"""

import json
from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web import http
from vumi.tests.utils import get_stubbed_worker, FakeRedis
from vumi.message import TransportUserMessage
from magriculture.workers.crop_prices import (Farmer, CropPriceModel,
                                              CropPriceWorker, FncsApi)


# Test data for farmers and prices

FARMERS = {
    '+27885557777': {
        "farmer_name": "Farmer Bob",
        "crops": [
            ["crop1", "Peas"],
            ["crop2", "Carrots"],
            ],
        "markets": [
            ["market1", "Kitwe"],
            ["market2", "Ndola"],
            ],
        },
    }

PRICES = {
    ("market1", "crop1", "unit1"): {
        "unit_name": "boxes",
        "prices": [1.2, 1.1, 1.5],
        },
    ("market1", "crop1", "unit2"): {
        "unit_name": "crates",
        "prices": [1.6, 1.7, 1.8],
        },
    }


class DummyResourceBase(Resource):
    """Base class for dummy resources."""

    isLeaf = True

    def render_GET(self, request):
        json_data = self.get_data(request)
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "application/json")
        return json.dumps(json_data)


class DummyFarmerResource(DummyResourceBase):
    """Dummy implementation of the /farmer/ HTTP api.

    /v1/farmer?msisdn=<MSISDN> maps to JSON with:

      * name: farmer's name
      * crops: list of crops of interest
      * markets: list of markets of interest
    """

    def __init__(self, farmers):
        Resource.__init__(self)
        self.farmers = farmers

    def get_data(self, request):
        msisdn = request.args["msisdn"][0]
        return self.farmers[msisdn]


class DummyPriceHistoryResource(DummyResourceBase):
    """Dummy implementation of the /price_history/ HTTP api.

    /v1/price_history?market=<id>&crop=<id>&unit=<id>&limit=<id> maps
    to JSON with:

      * prices: list of floats
    """
    def __init__(self, prices):
        Resource.__init__(self)
        self.prices = prices

    def get_data(self, request):
        market_id = request.args["market"][0]
        crop_id = request.args["crop"][0]
        limit = int(request.args.get("limit", [10])[0])
        price_data = {}
        for (market_id, crop_id, unit_id), value in self.prices.items():
            if market_id == market_id and crop_id == crop_id:
                price_data[unit_id] = {
                    "unit_name": value["unit_name"],
                    "prices": value["prices"][:limit],
                    }
        return price_data


class DummyFncsApiResource(Resource):
    def __init__(self, farmers, prices):
        Resource.__init__(self)
        self.putChild('farmer', DummyFarmerResource(farmers))
        self.putChild('price_history', DummyPriceHistoryResource(prices))


class TestFncsApi(unittest.TestCase):
    @inlineCallbacks
    def setUp(self):

        site_factory = Site(DummyFncsApiResource(FARMERS, PRICES))
        self.server = yield reactor.listenTCP(0, site_factory)
        addr = self.server.getHost()
        self.api = FncsApi("http://%s:%s/" % (addr.host, addr.port))

    @inlineCallbacks
    def tearDown(self):
        yield self.server.loseConnection()

    @inlineCallbacks
    def test_get_farmer(self):
        farmer_id = "+27885557777"
        data = yield self.api.get_farmer(farmer_id)
        self.assertEqual(data, {
            "farmer_name": FARMERS[farmer_id]["farmer_name"],
            "crops": FARMERS[farmer_id]["crops"],
            "markets": FARMERS[farmer_id]["markets"],
            })

    @inlineCallbacks
    def test_get_price_history(self):
        data = yield self.api.get_price_history("market1", "crop1", 2)
        self.assertEqual(data, {
            "unit1": {
                "unit_name": "boxes",
                "prices": PRICES[("market1", "crop1", "unit1")]["prices"][:2],
                },
            "unit2": {
                "unit_name": "crates",
                "prices": PRICES[("market1", "crop1", "unit2")]["prices"][:2],
                },
            })


class TestFarmer(unittest.TestCase):

    def test_serialize(self):
        farmer = Farmer("fakeid1", "Farmer Bob")
        farmer.crops.append(("cropid1", "Peas"))
        farmer.markets.append(("marketid1", "Small Town Market"))
        data = json.loads(farmer.serialize())
        self.assertEqual(data, {
            "user_id": "fakeid1",
            "farmer_name": "Farmer Bob",
            "crops": [["cropid1", "Peas"]],
            "markets": [["marketid1", "Small Town Market"]],
            })

    def test_unserialize(self):
        data = json.dumps({
            "user_id": "fakeid1",
            "farmer_name": "Farmer Bob",
            "crops": [["cropid1", "Peas"]],
            "markets": [["marketid1", "Small Town Market"]],
            })
        farmer = Farmer.unserialize(data)
        self.assertEqual(farmer.user_id, "fakeid1")
        self.assertEqual(farmer.farmer_name, "Farmer Bob")
        self.assertEqual(farmer.crops, [["cropid1", "Peas"]])
        self.assertEqual(farmer.markets, [["marketid1", "Small Town Market"]])

    @inlineCallbacks
    def test_from_user_id(self):
        site_factory = Site(DummyFncsApiResource(FARMERS, PRICES))
        server = yield reactor.listenTCP(0, site_factory)
        try:
            addr = server.getHost()
            api_url = "http://%s:%s/" % (addr.host, addr.port)
            api = FncsApi(api_url)
            farmer_id = "+27885557777"
            farmer = yield Farmer.from_user_id(farmer_id, api)
            self.assertEqual(farmer.user_id, "+27885557777")
            self.assertEqual(farmer.farmer_name, "Farmer Bob")
            self.assertEqual(farmer.crops, FARMERS[farmer_id]["crops"])
            self.assertEqual(farmer.markets, FARMERS[farmer_id]["markets"])
        finally:
            yield server.loseConnection()


class TestCropPriceModel(unittest.TestCase):
    @inlineCallbacks
    def setUp(self):
        site_factory = Site(DummyFncsApiResource(FARMERS, PRICES))
        self.server = yield reactor.listenTCP(0, site_factory)
        addr = self.server.getHost()
        self.api = FncsApi("http://%s:%s/" % (addr.host, addr.port))

    @inlineCallbacks
    def tearDown(self):
        yield self.server.loseConnection()

    def test_serialize(self):
        farmer = Farmer("fakeid1", "Farmer Bob")
        model = CropPriceModel(CropPriceModel.START, farmer, 1, None)
        data = json.loads(model.serialize())
        self.assertEqual(data, {
            "state": CropPriceModel.START,
            "farmer": farmer.serialize(),
            "selected_crop": 1,
            "selected_market": None,
            })

    def test_unserialize(self):
        farmer = Farmer("fakeid1", "Farmer Bob")
        data = json.dumps({
            "state": CropPriceModel.SELECT_CROP,
            "farmer": farmer.serialize(),
            "selected_crop": 1,
            "selected_market": 2,
            })
        model = CropPriceModel.unserialize(data)
        self.assertEqual(model.state, CropPriceModel.SELECT_CROP)
        self.assertEqual(model.selected_crop, 1)
        self.assertEqual(model.selected_market, 2)
        self.assertEqual(model.farmer.user_id, "fakeid1")
        self.assertEqual(model.farmer.farmer_name, "Farmer Bob")

    @inlineCallbacks
    def test_from_user_id(self):
        farmer_id = "+27885557777"
        model = yield CropPriceModel.from_user_id(farmer_id, self.api)
        self.assertEqual(model.state, CropPriceModel.START)
        self.assertEqual(model.selected_crop, None)
        self.assertEqual(model.selected_market, None)
        self.assertEqual(model.farmer.user_id, farmer_id)
        self.assertEqual(model.farmer.farmer_name,
                         FARMERS[farmer_id]["farmer_name"])
        self.assertEqual(model.farmer.crops, FARMERS[farmer_id]["crops"])
        self.assertEqual(model.farmer.markets, FARMERS[farmer_id]["markets"])

    @inlineCallbacks
    def test_process_event(self):
        farmer = Farmer("fakeid1", "Farmer Bob")
        farmer.add_crop("crop1", "Peas")
        farmer.add_market("market1", "Kitwe")
        model = CropPriceModel(CropPriceModel.START, farmer, 1, None)

        text, continue_session = yield model.process_event(None, self.api)
        self.assertEqual(text, "Hi Farmer Bob.\nSelect a crop:\n1. Peas")
        self.assertTrue(continue_session)

        text, continue_session = yield model.process_event("1", self.api)
        self.assertEqual(text, "Select a market:\n1. Kitwe")
        self.assertTrue(continue_session)
        self.assertEqual(model.selected_crop, 0)

        text, continue_session = yield model.process_event("1", self.api)
        self.assertEqual(text,
                         "Prices of Peas in Kitwe:\n"
                         "Sold as boxes:\n"
                         "  1.20\n  1.10\n  1.50\n"
                         "Sold as crates:\n"
                         "  1.60\n  1.70\n  1.80"
                         "Enter 1 for next market, 2 for previous market.\n"
                         "Enter 3 to exit.")
        self.assertTrue(continue_session)
        self.assertEqual(model.selected_market, 0)

        text, continue_session = yield model.process_event("3", self.api)
        self.assertEqual(text, "Goodbye!")
        self.assertFalse(continue_session)


class TestCropPriceWorker(unittest.TestCase):

    @inlineCallbacks
    def setUp(self):
        self.transport_name = 'test_transport'
        site_factory = Site(DummyFncsApiResource(FARMERS, PRICES))
        self.server = yield reactor.listenTCP(0, site_factory)
        addr = self.server.getHost()
        api_url = "http://%s:%s/" % (addr.host, addr.port)
        self.worker = get_stubbed_worker(CropPriceWorker, {
            'transport_name': self.transport_name,
            'worker_name': 'test_crop_prices',
            'api_url': api_url})
        self.broker = self.worker._amqp_client.broker
        yield self.worker.startWorker()
        self.fake_redis = FakeRedis()
        self.worker.session_manager.r_server = self.fake_redis

    @inlineCallbacks
    def tearDown(self):
        self.fake_redis.teardown()
        yield self.worker.stopWorker()
        yield self.server.loseConnection()

    # TODO: factor this out into a common application worker testing base class
    @inlineCallbacks
    def send(self, content, session_event=None):
        from_addr = list(FARMERS.keys())[0]
        msg = TransportUserMessage(content=content,
                                   session_event=session_event,
                                   from_addr=from_addr, to_addr='+5678',
                                   transport_name=self.transport_name,
                                   transport_type='fake',
                                   transport_metadata={})
        self.broker.publish_message('vumi', '%s.inbound' % self.transport_name,
                                    msg)
        yield self.broker.kick_delivery()

    # TODO: factor this out into a common application worker testing base class
    @inlineCallbacks
    def recv(self, n=0):
        msgs = yield self.broker.wait_messages('vumi', '%s.outbound'
                                                % self.transport_name, n)

        def reply_code(msg):
            if msg['session_event'] == TransportUserMessage.SESSION_CLOSE:
                return 'end'
            return 'reply'

        returnValue([(reply_code(msg), msg['content']) for msg in msgs])

    @inlineCallbacks
    def test_session_new(self):
        yield self.send(None, TransportUserMessage.SESSION_NEW)
        [reply] = yield self.recv(1)
        self.assertEqual(reply[0], "reply")
        self.assertTrue(reply[1].startswith("Hi Farmer Bob"))

    @inlineCallbacks
    def test_session_resume(self):
        yield self.send(None, TransportUserMessage.SESSION_NEW)
        yield self.send("1")
        [_start, reply] = yield self.recv(1)
        self.assertEqual(reply[0], "reply")
        self.assertTrue(reply[1].startswith("Select a market:"))

    @inlineCallbacks
    def test_session_close(self):
        yield self.send(None, TransportUserMessage.SESSION_CLOSE)
        replies = yield self.recv()
        self.assertEqual(replies, [])