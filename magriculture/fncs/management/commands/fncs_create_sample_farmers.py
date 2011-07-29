from django.core.management.base import BaseCommand
from magriculture.fncs.tests import utils
from magriculture.fncs.models.actors import Actor
from optparse import make_option

class Command(BaseCommand):
    help = "Generate sample farmer data"
    option_list = BaseCommand.option_list + (
        make_option('--total', dest='total', type='int', default=500, 
                        help='How many farmers to create'),
        make_option('--agent', dest='agent', type='str', default=None,
                        help='Generate farmers for a specific agent')
    )
    def handle(self, *args, **options):
        total = options['total']
        username = options['agent']
        if username:
            actor = Actor.objects.get(user__username=username)
            agent = actor.as_agent()
            self.generate_farmers(total, agent)
        else:
            self.generate_farmers(total)
        
    def generate_farmers(self, total, agent=None):
        for i in range(total):
            msisdn = 2776123456 + i
            
            # create a district
            district = utils.random_district()
            farmergroup_name = "%s Farmer Group" % (district.name,)
            
            # create the farmer
            farmer = utils.create_farmer(msisdn=str(msisdn), name=utils.random_name(),
                        surname=utils.random_surname(), farmergroup_name=farmergroup_name)
            
            # cultivates two types of crops
            farmer.grows_crop(utils.random_crop())
            farmer.grows_crop(utils.random_crop())
            
            # create the agent with msisdn offset of the total generated to
            # avoid collissions on usernames
            msisdn = msisdn + total + 1
            if not agent:
                agent = utils.create_agent(msisdn=str(msisdn), 
                            name=utils.random_name(),
                            surname=utils.random_surname())
            
            # create a market in the district
            market_name = '%s Market' % district.name
            market = utils.create_market(market_name, district)
            
            # have the farmer sells crops at that market through the agent
            farmer.sells_at(market, agent)
            
