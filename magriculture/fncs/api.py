"""FNCS HTTP API functions."""

import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from magriculture.fncs.models.actors import Actor
from magriculture.fncs.models.props import Transaction, Crop
from magriculture.fncs.models.geo import Market


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
