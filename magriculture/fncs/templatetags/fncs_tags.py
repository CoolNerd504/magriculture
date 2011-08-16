from django import template
from django.template.defaultfilters import floatformat
from magriculture.fncs.models.props import Transaction

register = template.Library()

SPARKLINE_COLOR = '98B785'
SPARKLINE_FILL_COLOR = '98B785'
SPARKLINE_LABEL_COLOR = '2E5333'
SPARKLINE_BACKGROUND = 'F7F8F4'
SPARKLINE_TEMPLATE = ''.join([
    'http://chart.apis.google.com/chart?',
    'cht=lc',
    '&chs=100x20',           # dimensions
    '&chd=t:%(values)s',    # csv delimited values
    '&chco=%s' % SPARKLINE_COLOR,
    '&chls=1,1,0',          # line style
    '&chm=o,%s,0,20,4' % SPARKLINE_LABEL_COLOR, # line fills
    '&chxt=r,x,y',          # visible axes
    '&chxs=0,%s,11,0,_|1,%s,1,0,_|2,%s,1,0,_' % (
        SPARKLINE_LABEL_COLOR, SPARKLINE_LABEL_COLOR, SPARKLINE_LABEL_COLOR
    ), # axis label styles
    '&chxl=0:|%(label)s|1:||2:||',  # custom axis labels
    '&chxp=0,%(position)s',         # custom axis positions
    '&chf=bg,s,%s' % SPARKLINE_BACKGROUND
])

def mean(floats):
    if len(floats) == 0:
        return float('nan')
    return sum(floats) / len(floats)

def deviation(value, average):
    return (float(value)/float(average) * 100)

@register.simple_tag
def average_crop_price(market, crop, unit):
    prices = list(Transaction.price_history_for(market, crop, unit)[:10])
    return floatformat(mean(prices), 2)

@register.simple_tag
def price_sparkline(market, crop, unit):
    prices = list(Transaction.price_history_for(market, crop, unit)[:10])
    last_price = prices[-1]
    average = mean(prices)
    values = [deviation(price, average) for price in prices]
    return sparkline(values, "%s ZMK" % int(last_price))

@register.filter
def sparkline(values, label='', position=50):
    return SPARKLINE_TEMPLATE % {
        'values': ','.join(str(v) for v in values),
        'label': label,
        'position': position
    }
    