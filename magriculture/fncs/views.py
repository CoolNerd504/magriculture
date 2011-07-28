from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render_to_response, get_object_or_404
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from datetime import datetime

from magriculture.fncs.models.actors import Farmer
from magriculture.fncs.models.props import Transaction, Crop
from magriculture.fncs import forms

@login_required
def home(request):
    return render_to_response('home.html', 
        context_instance=RequestContext(request))

@login_required
def farmers(request):
    farmers = Farmer.objects.all()
    q = request.GET.get('q','')
    if q:
        farmers = farmers.filter(actor__name__icontains=q)
    paginator = Paginator(farmers, 5)
    page = paginator.page(request.GET.get('p', 1))
    return render_to_response('farmers.html', {
        'paginator': paginator,
        'page': page,
        'q': q
    }, context_instance=RequestContext(request))

@login_required
def farmer_new(request):
    form = forms.FarmerForm()
    return render_to_response('farmers/new.html', {
        'form': form
    }, context_instance=RequestContext(request))

@login_required
def farmer_add(request):
    return HttpResponse('ok')

@login_required
def farmer(request, farmer_pk):
    return HttpResponseRedirect(reverse('fncs:farmer_sales', kwargs={
        'farmer_pk': farmer_pk
    }))

@login_required
def farmer_sales(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    paginator = Paginator(farmer.transactions(), 5)
    page = paginator.page(request.GET.get('p', 1))
    return render_to_response('farmers/sales.html', {
        'farmer': farmer,
        'paginator': paginator,
        'page': page,
    }, context_instance=RequestContext(request))
    
@login_required
def farmer_sale(request, farmer_pk, sale_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    transaction = get_object_or_404(Transaction, farmer=farmer, pk=sale_pk)
    return render_to_response('farmers/sale.html', {
        'farmer': farmer,
        'transaction': transaction,
    }, context_instance=RequestContext(request))

@login_required
def farmer_new_sale(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    form = forms.SelectCropForm()
    return render_to_response('farmers/new_sale.html', {
        'farmer': farmer,
        'form': form,
    }, context_instance=RequestContext(request))

@login_required
def farmer_new_sale_detail(request, farmer_pk):
    crop = get_object_or_404(Crop, pk=request.GET.get('crop'))
    farmer = get_object_or_404(Farmer, pk = farmer_pk)
    actor = request.user.get_profile()
    agent = actor.as_agent()
    
    redirect_to_farmer = HttpResponseRedirect(reverse('fncs:farmer', kwargs={
        'farmer_pk': farmer_pk
    }))
    if request.POST:
        if 'cancel' in request.POST:
            return redirect_to_farmer
        else:
            form = forms.TransactionForm(request.POST)
            if form.is_valid():
                crop = form.cleaned_data['crop']
                unit = form.cleaned_data['unit']
                price = form.cleaned_data['price']
                amount = form.cleaned_data['amount']
                market = form.cleaned_data['market']
                agent.register_sale(market, farmer, crop, unit, price, amount)
                messages.add_message(request, messages.INFO, 
                    "New Sale Registered")
                return redirect_to_farmer
            
    else:
        form = forms.TransactionForm(initial={
            'crop': crop.pk,
            'created_at': datetime.now()
        })
    
    return render_to_response('farmers/new_sale_detail.html', {
        'form': form,
        'crop': crop
    }, context_instance=RequestContext(request))
    
@login_required
def farmer_messages(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    return render_to_response('farmers/messages.html', {
        'farmer': farmer
    }, context_instance=RequestContext(request))

@login_required
def farmer_new_message(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    return render_to_response('farmers/new_message.html', {
        'farmer': farmer
    }, context_instance=RequestContext(request))

@login_required
def farmer_notes(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    return render_to_response('farmers/notes.html', {
        'farmer': farmer
    }, context_instance=RequestContext(request))

@login_required
def farmer_new_note(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    return render_to_response('farmers/new_note.html', {
        'farmer': farmer
    }, context_instance=RequestContext(request))

@login_required
def farmer_profile(request, farmer_pk):
    farmer = get_object_or_404(Farmer, pk=farmer_pk)
    return render_to_response('farmers/profile.html', {
        'farmer': farmer
    }, context_instance=RequestContext(request))

@login_required
def list_messages(request):
    return render_to_response('messages.html', {
    }, context_instance=RequestContext(request))

@login_required
def sales(request):
    return render_to_response('sales.html', {
    }, context_instance=RequestContext(request))

@login_required
def sales_crops(request):
    return render_to_response('sales_crops.html', {
    }, context_instance=RequestContext(request))

@login_required
def sales_agents(request):
    return render_to_response('sales_agents.html', {
    }, context_instance=RequestContext(request))

@login_required
def sales_agent_breakdown(request):
    return render_to_response('sales_agent_breakdown.html', {
    }, context_instance=RequestContext(request))


def todo(request):
    """Anything that resolves to here still needs to be completed"""
    return HttpResponse("This still needs to be implemented.")
