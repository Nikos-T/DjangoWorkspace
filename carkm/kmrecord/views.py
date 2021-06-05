from django.http.response import HttpResponseForbidden#, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from guardian.models.models import UserObjectPermission
from guardian.shortcuts import get_objects_for_user, assign_perm
from .models import Car, Record, FuelRecord, RichRecord, GasStation
from decimal import Decimal, DecimalException
from django.utils import timezone

# Create your views here.

# Page
@login_required
def cars(request):
	user = User.objects.get(username=request.user.username)
	context = {}
	context['cars'] = get_objects_for_user(user, 'kmrecord.view_car')
	return render(request, 'cars.html', context)


# Action
@login_required
def addCar(request):
	user = User.objects.get(username=request.user.username)
	if not user.has_perm('kmrecord.add_car'):
		return HttpResponseForbidden()

	licensePlate = request.POST['licensePlate']
	name = request.POST['name']
	comments = request.POST['comments']
	
	car = Car(licensePlate = licensePlate, name = name, comments = comments)
	car.save()

	groups = user.groups.all()
	for group in groups:
		assign_perm('kmrecord.view_car', group, car)
	assign_perm('kmrecord.change_car', user, car)
	assign_perm('kmrecord.delete_car', user, car)

	return redirect('kmrecord:Cars')


# Action
@login_required
def changeCar(request, licensePlate):
	user = User.objects.get(username=request.user.username)
	car = get_object_or_404(Car, licensePlate=licensePlate)
	if not user.has_perm('kmrecord.change_car', car):
		return HttpResponseForbidden()

	car.name = request.POST['name']
	car.comments = request.POST['comments']
	car.save()
	return redirect('kmrecord:Cars')


# Action
@login_required
def deleteCar(request, licensePlate):
	user = User.objects.get(username=request.user.username)
	car = get_object_or_404(Car, licensePlate=licensePlate)
	if not user.has_perm('kmrecord.delete_car', car):
		return HttpResponseForbidden()

	car.delete()
	return redirect('kmrecord:Cars')


# Page
@login_required
def car(request, licensePlate):
	user = User.objects.get(username=request.user.username)
	car = get_object_or_404(Car, licensePlate=licensePlate)
	if not user.has_perm('kmrecord.view_car', car):
		return HttpResponseForbidden()
	
	records = Record.objects.filter(car=car)
	context = {'car': car, 'records': records}
	return render(request, 'car.html', context)


# Action
@login_required
def addRecord(request, licensePlate):
	user = User.objects.get(username=request.user.username)
	car = get_object_or_404(Car, licensePlate=licensePlate)
	
	if (not user.has_perm('kmrecord.add_record')) or (not user.has_perm('kmrecord.view_car', car)):
		return HttpResponseForbidden()



	record = Record(km=request.POST['km'], date=request.POST['date'])
	record.car = car;
	saved = False

	groups = user.groups.all()

	if 'comments' in request.POST.keys():
		comments = request.POST['comments']
		if comments:
			richRecord = RichRecord(record=record)
			richRecord.__dict__.update(record.__dict__)
			richRecord.comments = comments
			richRecord.save()
			record.id = richRecord.id
			saved = True

	if {'pricePerLitre', 'price', 'quantity', 'gasStation', 'fuelType'} <= request.POST.keys():
		strCheck = True
		try:
			pricePerLitre = Decimal(request.POST['pricePerLitre'])
			quantity = Decimal(request.POST['quantity'])
			price = Decimal(request.POST['price'])
		except DecimalException:
			strCheck = False
		if strCheck and (all (value>0 for value in (pricePerLitre, quantity, price))):
			assert (abs(quantity * pricePerLitre - price)<= 0.01)
			fuelRecord = FuelRecord(record=record)
			fuelRecord.__dict__.update(record.__dict__)
			fuelRecord.pricePerLitre = pricePerLitre
			fuelRecord.quantity = quantity
			fuelRecord.price = price
			fuelRecord.fuelType = request.POST['fuelType']
			# Gas station special case as the user might create a new on request
			if len(request.POST['gasStation']):
				groupIds = ','.join([str(group.id) for group in groups])
				try:
					gasStation = GasStation.objects.raw('''
					SELECT ga.id, object_pk FROM guardian_groupobjectpermission gr
					INNER JOIN django_content_type c ON c.id = gr.content_type_id
					INNER JOIN kmrecord_gasstation ga ON gr.object_pk = ga.id
					WHERE gr.group_id IN ({}) AND c.app_label = 'kmrecord' AND c.model='gasstation' AND ga.name='{}'
					LIMIT 1;
					'''.format(groupIds, request.POST['gasStation']))[0]
				except IndexError:
					gasStation = GasStation(name=request.POST['gasStation'])
					gasStation.save()
					for group in groups:
						assign_perm('kmrecord.view_gasstation', group, gasStation)
					assign_perm('kmrecord.change_gasstation', user, gasStation)
					assign_perm('kmrecord.delete_gasstation', user, gasStation)
				fuelRecord.gasStation = gasStation

			fuelRecord.save()
			record.id = fuelRecord.id
			saved = True
	
	if not saved:
		record.save()
	
	assign_perm('kmrecord.change_record', user, record)
	assign_perm('kmrecord.delete_record', user, record)
	
	for group in groups:
		assign_perm('kmrecord.view_record', group, record)

	return redirect('kmrecord:Car', licensePlate=licensePlate)


# Action
@login_required
def changeRecord(request, recordId):
	user = User.objects.get(username=request.user.username)
	record = get_object_or_404(Record, id=recordId)
	if not user.has_perm('kmrecord.change_record', record):
		return HttpResponseForbidden()

	record.km = request.POST['km']
	record.date = request.POST['date']
	saved = False

	groups = user.groups.all()

	# handle comments: If comments exist either change richrecord or create a new
	# else if commments do not exist either remove existinh richrecord or do nothing
	if 'comments' in request.POST.keys():
		comments = request.POST['comments']
		if comments:
			try:
				richRecord = record.richrecord
			except RichRecord.DoesNotExist:
				richRecord = RichRecord(record=record)
				richRecord.__dict__.update(record.__dict__)
			richRecord.comments = comments
			richRecord.save()
			saved = True
		else:
			try:
				richRecord = record.richrecord
				richRecord.delete(keep_parents=True)
			except RichRecord.DoesNotExist:
				pass

	# handle fuel stats: If fuel stats > 0 either change fuelrecord or create a new
	# else if a fuel stat <= 0 delete fuelRecord
	if {'pricePerLitre', 'price', 'quantity', 'gasStation', 'fuelType'} <= request.POST.keys():
		strCheck = True
		try:
			pricePerLitre = Decimal(request.POST['pricePerLitre'])
			quantity = Decimal(request.POST['quantity'])
			price = Decimal(request.POST['price'])
		except DecimalException:
			strCheck = False
		if strCheck and (all (value>0 for value in (pricePerLitre, quantity, price))):
			assert (abs(quantity * pricePerLitre - price)<= 0.01)
			try:
				fuelRecord = record.fuelrecord
				print('found!')
			except FuelRecord.DoesNotExist:
				print('creating')
				fuelRecord = FuelRecord(record=record)
				fuelRecord.__dict__.update(record.__dict__)
			fuelRecord.pricePerLitre = pricePerLitre
			fuelRecord.quantity = quantity
			fuelRecord.price = price
			fuelRecord.fuelType = request.POST['fuelType']
			# Gas station special case as the user might create a new on request
			if len(request.POST['gasStation']):
				groupIds = ','.join([str(group.id) for group in groups])
				try:
					gasStation = GasStation.objects.raw('''
					SELECT ga.id, object_pk FROM guardian_groupobjectpermission gr
					INNER JOIN django_content_type c ON c.id = gr.content_type_id
					INNER JOIN kmrecord_gasstation ga ON gr.object_pk = ga.id
					WHERE gr.group_id IN ({}) AND c.app_label = 'kmrecord' AND c.model='gasstation' AND ga.name='{}'
					LIMIT 1;
					'''.format(groupIds, request.POST['gasStation']))[0]
				except IndexError:
					gasStation = GasStation(name=request.POST['gasStation'])
					gasStation.save()
					for group in groups:
						assign_perm('kmrecord.view_gasstation', group, gasStation)
					assign_perm('kmrecord.change_gasstation', user, gasStation)
					assign_perm('kmrecord.delete_gasstation', user, gasStation)
				fuelRecord.gasStation = gasStation
				
			fuelRecord.save()
			record.id = fuelRecord.id
			saved = True
		else:
			try:
				fuelRecord = record.fuelrecord
				fuelRecord.delete(keep_parents=True)
			except FuelRecord.DoesNotExist:
				pass

	if not saved:
		record.save()
	
	return redirect('kmrecord:Car', licensePlate=record.car.licensePlate)


# Action
@login_required
def deleteRecord(request, recordId):
	user = User.objects.get(username=request.user.username)
	record = get_object_or_404(Record, id=recordId)
	if not user.has_perm('kmrecord.delete_record', record):
		return HttpResponseForbidden()

	record.delete()
	return redirect('kmrecord:Car', licensePlate=record.car.licensePlate)


# Page
@login_required
def record(request, recordId):
	user = User.objects.get(username=request.user.username)
	record = get_object_or_404(Record, id=recordId)
	if not user.has_perm('kmrecord.view_record', record):
		return HttpResponseForbidden()
	
	context = {'fuelRecord': None, 'comments': ''}
	try:
		fuelRecord = record.fuelrecord
	except FuelRecord.DoesNotExist:
		fuelRecord = FuelRecord(record=record)	# Create it for context but do not save it (yet)
		fuelRecord.__dict__.update(record.__dict__)
	context['fuelRecord'] = fuelRecord

	try:
		richRecord = record.richrecord
		context['comments'] = richRecord.comments # RichRecord only appends a field comments
	except RichRecord.DoesNotExist:
		pass
	return render(request, 'record.html', context)


# Page
@login_required
def createRecord(request, licensePlate):
	user = User.objects.get(username=request.user.username)
	car = get_object_or_404(Car, licensePlate=licensePlate)
	if not user.has_perm('kmrecord.view_car', car) or not user.has_perm('kmrecord.add_record'):
		return HttpResponseForbidden()
	
	#userCreated = UserObjectPermission.objects.select_related('content_type').filter(content_type__app_label='kmrecord', content_type__model='record', user_id=user.id)
	try:
		lastCarRecord = Record.objects.filter(car__licensePlate=licensePlate).order_by('-id')[0]
	except IndexError:
		lastCarRecord = Record(car=car)

	context = {'fuelRecord': None, 'comments': '', 'gasStations':get_objects_for_user(user, 'kmrecord.view_gasstation')}
	try:
		fuelRecord = lastCarRecord.fuelrecord
	except FuelRecord.DoesNotExist:
		fuelRecord = FuelRecord(record=lastCarRecord)
		fuelRecord.__dict__.update(lastCarRecord.__dict__)
	fuelRecord.id = None # In order to create a new one
	fuelRecord.date = timezone.now()
	fuelRecord.quantity = Decimal('0.000')
	fuelRecord.price = Decimal('0.00')
	context['fuelRecord'] = fuelRecord

	return render(request, 'record.html', context)


# Page
@login_required
def gasStations(request):
	user = User.objects.get(username=request.user.username)
	context = {}
	context['gasStations'] = get_objects_for_user(user, 'kmrecord.view_gasstation')
	print(context)
	return render(request, 'gasstations.html', context)


# Action
@login_required
def addGasStation(request):
	user = User.objects.get(username=request.user.username)
	if not user.has_perm('kmrecord.add_gasstation'):
		return HttpResponseForbidden()

	name = request.POST['name']
	url = request.POST['url']

	gasStation = GasStation(name = name, url = url)
	gasStation.save()

	groups = user.groups.all()
	for group in groups:
		assign_perm('kmrecord.view_gasstation', group, gasStation)
	assign_perm('kmrecord.change_gasstation', user, gasStation)
	assign_perm('kmrecord.delete_gasstation', user, gasStation)

	return redirect('kmrecord:GasStations')


# Action
@login_required
def changeGasStation(request, gasStationId):
	user = User.objects.get(username=request.user.username)
	gasStation = get_object_or_404(GasStation, id=gasStationId)
	if not user.has_perm('kmrecord.change_gasstation', gasStation):
		return HttpResponseForbidden()

	gasStation.name = request.POST['name']
	gasStation.url = request.POST['url']
	gasStation.save()
	return redirect('kmrecord:GasStations')


# Action
@login_required
def deleteGasStation(request, gasStationId):
	user = User.objects.get(username=request.user.username)
	gasStation = get_object_or_404(GasStation, id=gasStationId)
	if not user.has_perm('kmrecord.delete_gasstation', gasStation):
		return HttpResponseForbidden()

	gasStation.delete()
	return redirect('kmrecord:GasStations')