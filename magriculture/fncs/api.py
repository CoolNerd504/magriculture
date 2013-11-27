"""FNCS HTTP API functions."""
# Python
import json
import hashlib
import random

# Django
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

# Project
from magriculture.fncs.models.actors import Actor, Farmer, Agent
from magriculture.fncs.models.props import Transaction, Crop
from magriculture.fncs.models.geo import Market, Ward, District

# Thirdparty
from tastypie.resources import ModelResource, ALL_WITH_RELATIONS, ALL
from tastypie.authorization import Authorization
from tastypie import fields


def strip_in_country_codes(msisdn):
    """Strips the country code for numbers that are considered to
       be in-country for this deployment. Other numbers are left
       as-is.
       """
    for (code, prefix) in settings.MAGRICULTURE_IN_COUNTRY_CODES:
        if msisdn.startswith(code):
            msisdn = prefix + msisdn[len(code):]
            break
    return msisdn


def get_farmer(request):
    msisdn = request.GET.get('msisdn')
    if msisdn is None:
        return HttpResponse(json.dumps({"reason": "No msisdn given."}),
                            status=400)
    msisdn = strip_in_country_codes(msisdn)
    # Something's wrong with our db, we've got multiple
    # farmers for the same actor.
    try:
        farmer = Actor.find(msisdn).as_farmer()
    except ObjectDoesNotExist:
        return HttpResponse(json.dumps({"reason": "No farmer found."}),
                            status=404)
    crops = [(crop.pk, crop.name) for crop in farmer.crops.all()]
    markets = [(market.pk, market.name) for market in farmer.markets.all()]
    farmer_data = {
        "farmer_name": farmer.actor.name,
        "crops": crops,
        "markets": markets,
    }
    return HttpResponse(json.dumps(farmer_data))


def get_price_history(request):
    market_pk = request.GET.get('market')
    crop_pk = request.GET.get('crop')
    limit = int(request.GET.get('limit', '10'))
    market = get_object_or_404(Market, pk=market_pk)
    crop = get_object_or_404(Crop, pk=crop_pk)
    prices = {}
    for unit in crop.units.all():
        unit_prices = Transaction.price_history_for(market, crop, unit)[:limit]
        unit_prices = list(unit_prices)
        if unit_prices:
            prices[unit.pk] = {
                "unit_name": unit.name,
                "prices": unit_prices,
            }
    return HttpResponse(json.dumps(prices))


def get_highest_markets(request):
    crop_pk = request.GET.get('crop')
    limit = int(request.GET.get('limit', '10'))
    crop = get_object_or_404(Crop, pk=crop_pk)
    highest_markets = [(market.pk, market.name) for market
                       in Market.highest_markets_for(crop)[:limit]]
    return HttpResponse(json.dumps(highest_markets))


def get_markets(request):
    limit = int(request.GET.get('limit', '10'))
    markets = [(market.pk, market.name) for market
               in Market.objects.all()[:limit]]
    return HttpResponse(json.dumps(markets))


class UserResource(ModelResource):
    """
    Creating a user
    ::

         url: <base_url>/api/v1/user/
         method: POST
         content_type: "application/json"
         body: {
                    Paragrapth title..
                    username": "27721231234",
                    "first_name": "test_first_name",
                    "last_name": "test_last_name"
         }
    """
    class Meta:
        queryset = User.objects.all()
        resource_name = "user"
        list_allowed_methods = ['post', 'get', 'put']
        authorization = Authorization()
        include_resource_uri = True
        always_return_data = True
        excludes = ['is_active', 'is_staff', 'is_superuser',
                    'date_joined', 'last_login']
        filtering = {"id" : ALL,
                     "username": ALL}

    def get_object_list(self, request):
        """
        Remove super user and staff from object list for security purposes
        """
        query = super(UserResource, self).get_object_list(request)
        query = query.filter(is_staff=False).filter(is_superuser=False)
        return query

    def hydrate(self, bundle):
        """
        - Setting password to None on make_password so as to prevent user login
        - Setting is_staff and is_superuser to False for extra security
        """
        if "is_superuser" in bundle.data:
            bundle.data["is_superuser"] = False

        if "is_staff" in bundle.data:
            bundle.data["is_staff"] = False

        bundle.data["password"] = make_password(None)
        return bundle

    def dehydrate(self, bundle):
        if "password" in bundle.data:
            del bundle.data["password"]

        if "is_staff" in bundle.data:
            del bundle.data["is_staff"]

        if "is_superuser" in bundle.data:
            del bundle.data["is_superuser"]

        return bundle


class FarmerResource(ModelResource):
    """
    Creating a new farmer requires several:

    1. Create a User
    2. On created user filter for Actor based on user.id or msisdn
    3. Get crop data, can filter by name based on user input
    4. Get ward, can filter by name
    5. Get district, can filter by name
    6. Create the farmer using above responses
    ::

        url: <base_url>/api/v1/farmer/
        method: POST
        content_type: application/json
        body: {
                    "actor": "/api/v1/actor/%s/" % response_for_actor["objects"][0]["id"],
                    "agents": "",
                    "crops": ["/api/v1/crop/%s/" % response_for_crop["objects"][0]["id"]],
                    "districts": ["/api/v1/district/%s/" % response_for_district["objects"][0]["id"]],
                    "hh_id": "",
                    "id_number": "123456789",
                    "markets": "",
                    "participant_type": "",
                    "resource_uri": "",
                    "wards": ["/api/v1/ward/%s/" % response_for_ward["objects"][0]["id"]]
                }

    """
    agents = fields.ManyToManyField('magriculture.fncs.api.AgentsResource',
                                    'agents',
                                    full=True)
    actor = fields.ForeignKey('magriculture.fncs.api.ActorResource',
                                    'actor',
                                    full=True)

    markets = fields.ManyToManyField('magriculture.fncs.api.MarketResource',
                                    'markets',
                                    full=True)

    wards = fields.ManyToManyField('magriculture.fncs.api.WardResource',
                                    'wards',
                                    full=True)

    districts = fields.ManyToManyField('magriculture.fncs.api.DistrictResource',
                                    'districts',
                                    full=True)

    crops = fields.ManyToManyField('magriculture.fncs.api.CropResource',
                                    'crops',
                                    full=True)

    class Meta:
        queryset = Farmer.objects.all()
        resource_name = "farmer"
        list_allowed_methods = ['post', 'get', 'put']
        authorization = Authorization()
        include_resource_uri = True
        always_return_data = True


class AgentsResource(ModelResource):
    """
    Get the agents in the system
    ::

        url: <base_url>/api/v1/agent/
        method: GET
    """
    class Meta:
        queryset = Agent.objects.all()
        resource_name = "agent"
        authorization = Authorization()
        list_allowed_methods = ['get']
        include_resource_uri = True
        always_return_data = True


class ActorResource(ModelResource):
    """
    Returns the actors in the system and can filter on id or msisdn as username
    ::

        url: <base_url>/api/v1/actor/
        url: <base_url>/api/v1/actor/?user__username=123456789
        url: <base_url>/api/v1/actor/?user__id=1
        method": GET

    """
    user = fields.ToOneField("magriculture.fncs.api.UserResource",
                             'user',
                             full=True)
    class Meta:
        queryset = Actor.objects.all()
        resource_name = "actor"
        authorization = Authorization()
        list_allowed_methods = ['get']
        include_resource_uri = True
        always_return_data = True
        filtering = {"user" : ALL_WITH_RELATIONS}


class MarketResource(ModelResource):
    """
    Returns the market in the system and can filter by name
    ::

        url: <base_url>/api/v1/market/
        url: <base_url>/api/v1/market/?name=TheName
        method: GET
    """
    class Meta:
        queryset = Market.objects.all()
        resource_name = "market"
        authorization = Authorization()
        list_allowed_methods = ['get']
        include_resource_uri = True
        always_return_data = True
        filtering = {"name" : ALL}


class WardResource(ModelResource):
    """
    Returns the ward in the system and can filter by name
    ::

        url: <base_url>/api/v1/ward/
        url: <base_url>/api/v1/ward/?name=TheName

        method: GET
    """
    class Meta:
        queryset = Ward.objects.all()
        resource_name = "ward"
        authorization = Authorization()
        list_allowed_methods = ['get']
        include_resource_uri = True
        always_return_data = True
        filtering = {"name" : ALL}


class DistrictResource(ModelResource):
    """
    Returns the districts in the system and can filter by name
    ::

        url: <base_url>/api/v1/district/
        url: <base_url>/api/v1/district/?name=TheName
        method: GET

    """
    class Meta:
        queryset = District.objects.all()
        resource_name = "district"
        authorization = Authorization()
        list_allowed_methods = ['get']
        include_resource_uri = True
        always_return_data = True
        filtering = {"name" : ALL}


class CropResource(ModelResource):
    """
    Returns the Crops in the system and can filter by name
    ::

        url: <base_url>/api/v1/crop/
        url: <base_url>/api/v1/crop/?name=TheName
        method: GET
    """
    class Meta:
        queryset = Crop.objects.all()
        resource_name = "crop"
        authorization = Authorization()
        list_allowed_methods = ['get']
        include_resource_uri = True
        always_return_data = True
        filtering = {"name" : ALL_WITH_RELATIONS}
