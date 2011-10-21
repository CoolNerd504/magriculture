from django.test import TestCase
from django.contrib.auth.models import User
from magriculture.fncs.tests import utils
from magriculture.fncs.models.actors import Actor, Farmer, FarmerGroup
from magriculture.fncs.models.props import Message, GroupMessage, Note
from datetime import datetime, timedelta


class ActorTestCase(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_actor_creation(self):
        user = User.objects.create_user('username','email@domain.com')
        actor = user.get_profile()
        self.assertTrue(isinstance(actor, Actor))


class AgentTestCase(TestCase):
    def test_agent_creation(self):
        agent = utils.create_agent()
        self.assertEquals(agent.farmers.count(), 0)
        self.assertEquals(agent.markets.count(), 0)

    def test_agent_sale(self):
        farmer = utils.create_farmer()
        market = utils.create_market("market", farmer.farmergroup.district)
        agent = utils.create_agent()

        crop = utils.create_crop("potatoes")
        unit = utils.create_crop_unit("boxes")
        price = 20
        amount = 10

        # create inventory
        receipt = agent.take_in_crop(market, farmer, amount, unit, crop)
        self.assertTrue(receipt.remaining_inventory(), 10)
        transaction = agent.register_sale(receipt, amount, price)

        self.assertTrue(agent.is_selling_for(farmer, market))
        self.assertIn(market, agent.markets.all())
        self.assertIn(farmer, agent.farmers.all())
        # test the transaction aspect
        self.assertEquals(transaction.total, 200.0)
        self.assertEquals(transaction.price, price)
        self.assertEquals(transaction.amount, amount)
        # test the selling out of the inventory
        crop_receipt = transaction.crop_receipt
        self.assertEquals(crop_receipt.crop, crop)
        self.assertEquals(crop_receipt.unit, unit)
        self.assertEquals(crop_receipt.agent, agent)
        self.assertEquals(crop_receipt.farmer, farmer)
        self.assertEquals(crop_receipt.market, market)

        # had 20 crops in inventory, inventory should be reconciled
        # and the calculated stock count should reflect this
        self.assertEquals(crop_receipt.amount, 10)
        self.assertTrue(crop_receipt.reconciled)
        self.assertEquals(crop_receipt.remaining_inventory(), 0)

        self.assertAlmostEqual(transaction.created_at, datetime.now(),
            delta=timedelta(seconds=2))
        self.assertIn(transaction, farmer.transactions())
        self.assertTrue(farmer.is_growing_crop(crop))
        self.assertIn(transaction, agent.sales_for(farmer))

    def test_actor_as_agent(self):
        agent = utils.create_agent()
        actor = agent.actor
        self.assertEquals(agent, actor.as_agent())

    def test_agent_crop_receipt_inventory(self):
        farmer1 = utils.create_farmer(msisdn="27700000000")
        farmer2 = utils.create_farmer(msisdn="27700000001")
        market = utils.create_market("market", farmer1.farmergroup.district)
        agent = utils.create_agent()
        receipt1 = utils.take_in(market, agent, farmer1, 10, 'box', 'tomato')
        receipt2 = utils.take_in(market, agent, farmer2, 10, 'box', 'onion')
        self.assertEqual([receipt1], list(agent.cropreceipts_available_for(farmer1)))
        self.assertEqual([receipt2], list(agent.cropreceipts_available_for(farmer2)))

    def test_send_farmer_message(self):
        farmer = utils.create_farmer()
        agent = utils.create_agent()
        message = agent.send_message_to_farmer(farmer, 'hello world')
        self.assertIn(message, Message.objects.filter(sender=agent.actor,
            recipient=farmer.actor))

    def test_send_farmergroup_message(self):
        farmer1 = utils.create_farmer(farmergroup_name="group 1")
        farmer2 = utils.create_farmer(farmergroup_name="group 2")
        farmergroups = FarmerGroup.objects.all()
        agent = utils.create_agent()
        agent.send_message_to_farmergroups(farmergroups, 'hello world')
        self.assertTrue(agent.actor.sentmessages_set.count(), 2)
        self.assertTrue(GroupMessage.objects.count(), 2)
        self.assertTrue(farmer1.actor.receivedmessages_set.count(), 1)
        self.assertTrue(farmer2.actor.receivedmessages_set.count(), 1)

    def test_write_note(self):
        farmer = utils.create_farmer()
        agent = utils.create_agent()
        note = agent.write_note(farmer, 'this is a note about the farmer')
        self.assertIn(note, Note.objects.all())
        self.assertIn(note, farmer.actor.attachednote_set.all())
        self.assertIn(note, agent.notes_for(farmer))



class MarketMonitorTestCase(TestCase):

    def test_market_monitor_registration(self):
        monitor = utils.create_market_monitor()
        province = utils.create_province("province")
        rpiarea = utils.create_rpiarea("rpiarea")
        rpiarea.provinces.add(province)
        district = utils.create_district("district", province)
        market = utils.create_market("market", district)

        crop = utils.create_crop("potatoes")
        unit = utils.create_crop_unit("boxes")
        price_floor = 150
        price_ceiling = 200

        offer = monitor.register_offer(market, crop, unit, price_floor, price_ceiling)
        self.assertTrue(monitor.is_monitoring(market))
        self.assertIn(market, monitor.markets.all())
        for rpiarea in market.rpiareas():
            self.assertIn(rpiarea, monitor.rpiareas.all())
        self.assertEquals(offer.price_floor, 150.0)
        self.assertEquals(offer.price_ceiling, 200.0)
        self.assertEquals(offer.crop, crop)
        self.assertEquals(offer.unit, unit)
        self.assertEquals(offer.market, market)
        self.assertAlmostEqual(offer.created_at, datetime.now(),
            delta=timedelta(seconds=2))



class FarmerTestCase(TestCase):

    def test_farmer_create_helper(self):
        rpiarea = utils.create_rpiarea("rpiarea")
        zone = utils.create_zone("zone", rpiarea)
        province = utils.create_province("province")
        district = utils.create_district("district", province)
        ward = utils.create_ward("ward", district)
        farmergroup = utils.create_farmergroup("fg", zone, district, ward)
        self.assertFalse(Farmer.objects.exists())
        farmer1 = Farmer.create("0761234567", "name", "surname", farmergroup)
        self.assertTrue(Farmer.objects.count(), 1)
        self.assertEqual(farmer1.actor.name, 'name surname')
        farmer2 = Farmer.create("0761234567", "new name", "new surname", farmergroup)
        self.assertTrue(Farmer.objects.count(), 1)
        self.assertEqual(farmer2.actor.name, 'new name new surname')

    def test_farmer_creation(self):
        farmer = utils.create_farmer(name="joe")
        self.assertEquals(farmer.actor.user.first_name, "joe")
        self.assertEquals(farmer.farmergroup.name, "farmer group")
        self.assertEquals(farmer.agents.count(), 0)

    def test_farmer_agent_link(self):
        farmer = utils.create_farmer()
        market = utils.create_market("market", farmer.farmergroup.district)
        agent = utils.create_agent()

        crop = utils.create_crop("potatoes")
        unit = utils.create_crop_unit("boxes")
        amount = 10

        receipt = agent.take_in_crop(market, farmer, amount, unit, crop)

        self.assertTrue(agent.is_selling_for(farmer, market))
        self.assertIn(market, agent.markets.all())
        self.assertIn(farmer, agent.farmers.all())
        self.assertIn(market, farmer.markets.all())

    def test_farmer_districts(self):
        province = utils.create_province("province")
        district1 = utils.create_district("district 1", province)
        market1 = utils.create_market("market 1", district1)

        district2 = utils.create_district("district 2", province)
        market2 = utils.create_market("market 2", district2)

        farmer = utils.create_farmer()
        agent1 = utils.create_agent("agent 1")
        agent2 = utils.create_agent("agent 2")

        farmer.operates_at(market1, agent1)
        farmer.operates_at(market2, agent2)

        self.assertEquals(farmer.districts().count(), 2)
        self.assertIn(district1, farmer.districts())
        self.assertIn(district2, farmer.districts())

    def test_farmer_grows_crops(self):
        farmer = utils.create_farmer()
        crop = utils.random_crop()
        farmer.grows_crop(crop)
        self.assertIn(crop, farmer.crops.all())

    def test_farmer_creation(self):
        district = utils.random_district()
        rpiarea = utils.create_rpiarea("rpiarea")
        zone = utils.create_zone("zone", rpiarea)
        ward = utils.create_ward("ward", district)
        farmergroup = utils.create_farmergroup("farmer group", zone, district, ward)
        farmer = Farmer.create('27761234567', 'first', 'last', farmergroup)
        self.assertEquals(farmer.actor.name, 'first last')
        self.assertEquals(farmer.actor.user.username, '27761234567')

    def test_farmer_market_setting(self):
        farmer = utils.create_farmer()
        market1 = utils.create_market("market 1", farmer.farmergroup.district)
        market2 = utils.create_market("market 2", farmer.farmergroup.district)
        market3 = utils.create_market("market 3", farmer.farmergroup.district)
        # prime the farmer with 1 market
        farmer.markets.add(market1)
        # test the destructive set
        farmer.operates_at_markets_exclusively([market2,market3])
        self.assertNotIn(market1, farmer.markets.all())
        self.assertIn(market2, farmer.markets.all())
        self.assertIn(market3, farmer.markets.all())

    def test_farmer_crop_setting(self):
        farmer = utils.create_farmer()
        crop1 = utils.create_crop("apples")
        crop2 = utils.create_crop("oranges")
        crop3 = utils.create_crop("potatoes")
        farmer.grows_crop(crop1)
        self.assertIn(crop1, farmer.crops.all())
        farmer.grows_crops_exclusively([crop2, crop3])
        self.assertNotIn(crop1, farmer.crops.all())
        self.assertIn(crop2, farmer.crops.all())
        self.assertIn(crop3, farmer.crops.all())
