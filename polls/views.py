'''Views for app polls'''
import datetime
from django.shortcuts import render
# Create your views here.
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.template import loader
from django.shortcuts import get_object_or_404
from django.views import generic
from django.utils import timezone
from django.db import connection
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Flight, Airline, Customer, Airport, Customer, Account, ReservationInfo, RfRelation, ReservationFlight
# from .models import Question_new, Choice_new


def index_default(request):
    '''Substitiued by IndexView, which is a template provide by Django'''
    # latest_question_list = Question_new.objects.order_by('-pub_date')[:5]
    airports = Airport.objects.filter()
    template = loader.get_template('polls/index.html')
    context = {
        'airports': airports,
    }
    return HttpResponse(template.render(context, request))


def index_warning(request):
    '''Substitiued by IndexView, which is a template provide by Django'''
    airports = Airport.objects.filter()
    template = loader.get_template('polls/index.html')
    context = {
        'airports': airports,
        'warning': True,
    }
    return HttpResponse(template.render(context, request))


def login_page(request):
    '''
    Login page logic, can login as customer or manager
    '''
    email = request.POST['email']
    password = request.POST['password']
    user = authenticate(request, username=email, password=password)
    if user is not None:
        login(request, user)
        # Redirect to a success page.
        return HttpResponseRedirect(reverse('polls:index_default'))
    else:
        # Return an 'invalid login' error message.
        return HttpResponseRedirect(reverse('polls:index_warning'))


def logout_page(request):
    '''
    Log out and delete all session data
    '''
    logout(request)
    return HttpResponseRedirect(reverse('polls:index_default'))


def search(request):
    '''
    Logic to search flight
    '''
    template = loader.get_template('polls/search.html')
    from_location = request.POST['from']
    from_location = from_location[1:4]
    to_location = request.POST['to']
    to_location = to_location[1:4]
    # Put passenger number into session for book use
    passenger = request.POST['passenger_number']
    request.session['passenger'] = passenger

    leave_date = timezone.now(
    ) if request.POST['leave'] is None else request.POST['leave']
    leave_date_tom = getTomorrowDate(leave_date)
    leave_day = getDayFromDate(leave_date)

    return_date = (timezone.now() + datetime.timedelta(days=1)
                   ) if request.POST['return'] is None else request.POST['return']
    return_day = getDayFromDate(return_date)

    # Get direct flight
    request.session['direct_flight'] = {}
    direct_result = Flight.objects.filter(Q(depart_airport=from_location) &
                                          Q(arrive_airport=to_location) & (Q(workday=((leave_day+1) % 2)) | Q(workday=(leave_day % 2))),)
    for i, d_f in enumerate(direct_result):
        if d_f.workday == leave_day % 2:
            d_f.workday = leave_date
        else:
            d_f.workday = leave_date_tom
        d_f.id = str(i)
        # Put direct flight FID into into session for book use
        # We also need to save leave date
        request.session['direct_flight'][i] = str(d_f.fid)+","+d_f.workday
        request.session.modified = True

    # Get one_stop flight
    one_stop = one_stop_flight(
        from_location, to_location, leave_day % 2, (leave_day+1) % 2)
    one_stop_result = set()
    for f in one_stop:
        airline1 = Airline.objects.get(airline_id=f[0]).airline_name
        airline2 = Airline.objects.get(airline_id=f[8]).airline_name
        date1 = leave_date if f[3] == leave_day % 2 else leave_date_tom
        date2 = leave_date if f[11] == leave_day % 2 else leave_date_tom
        d1 = str(Airport.objects.get(airport_id=f[5]))
        a1 = str(Airport.objects.get(airport_id=f[7]))
        d2 = str(Airport.objects.get(airport_id=f[13]))
        a2 = str(Airport.objects.get(airport_id=f[15]))
        f = (airline1,) + f[1:3] + (str(date1),) + (str(f[4]),) + (d1,) + \
            (str(f[6]),) + (a1,) + (airline2,) + f[9:11] + (str(date2),) + \
            (str(f[12]),) + (d2,) + (str(f[14]),) + (a2,)
        one_stop_result.add(f)
    # Distinguish between jump from search to book and buy to book(back due to duplicate names)
    request.session['duplicate_name'] = None
    request.session['book_fid'] = None
    request.session['leave_date'] = None
    context = {
        'direct_flight': direct_result,
        'one_stop_flight': one_stop_result,
        'leave_date': leave_date,
        'return_date': return_date,
    }
    return HttpResponse(template.render(context, request))


@login_required(login_url='/polls/')
def book(request):
    template = loader.get_template('polls/book.html')
    # Get flight related data
    # We may jump back because passenger name duplicate
    # In this case we do not get fid and date by POST
    if request.session['duplicate_name'] is None:
        fid, date = request.session['direct_flight'][request.POST['id']].split(
            ",")
    else:
        fid = request.session['book_fid']
        date = request.session['leave_date']
    flight = Flight.objects.get(fid=fid)
    flight.workday = date
    if flight.arrive_time.hour < flight.depart_time.hour:
        flight.arrive_date = getTomorrowDate(flight.workday)
        flight.fly_hour = flight.arrive_time.hour + 24 - flight.depart_time.hour
    else:
        flight.arrive_date = flight.workday
        flight.fly_hour = flight.arrive_time.hour - flight.depart_time.hour
    # Get account data
    user = request.user
    # In original db Customer table, we use email as username to log in
    # But in Django auth.user, by default it uses only username and password to log in
    # So we first import all data in Customer table to default auth.user table
    # and set email as username
    cus = Customer.objects.get(email=user.username)
    accounts = Account.objects.filter(customer__customer_id=cus.customer_id)
    # Need to get unique account id and account credit card
    account_hash = set()
    for acc in accounts:
        account_hash.add(str(acc.account_id)+","+str(acc.credit_card))
    account_unique = list()
    for hash in account_hash:
        id, credit_card = hash.split(",")
        ac = {}
        ac['account_id'] = id
        ac['credit_card'] = credit_card
        account_unique.append(ac)
    try:
        loop_times = int(request.session['passenger'])
    except ValueError:
        loop_times = 1
    context = {
        'flight': flight,
        'passenger_loop_times': range(loop_times),
        'accounts': account_unique,
        'duplicate_name': request.session['duplicate_name']
    }
    return HttpResponse(template.render(context, request))


@login_required(login_url='/polls/')
def buy(request):
    '''
    Write new reservation data into DB
    1.Reservation-Info - 2.Account - 3.RF-Relation - 4.Reservation-Flight
    '''
    # First we need to check if that flight already have thsoe customers
    fid = request.POST['fid']  # Flight ID, unique
    request.session['book_fid'] = fid
    leave_date = request.POST['leave_date']  # Flight leave date
    request.session['leave_date'] = leave_date
    try:
        # check how many passengers this time
        loop_times = int(request.session['passenger'])
    except ValueError:
        loop_times = 1
    # check db get all names in that flight
    exist_passengers = exist_passenger(fid, leave_date)
    new_passengers = []
    for i in range(loop_times):  # Get new passengers this time
        index = i+1
        new_passengers.append(str(request.POST["name"+str(index)]))
    name_duplicate = False
    duplicate_name = ""
    if exist_passengers:
        for ex_name in exist_passengers:
            for new_name in new_passengers:
                if ex_name[0].lower() == new_name.lower():
                    name_duplicate = True
                    duplicate_name = new_name
                    break
            if name_duplicate:
                break
    # If name has duplication, we redirect it to buy page with warning
    if name_duplicate:
        request.session['duplicate_name'] = duplicate_name
        return HttpResponseRedirect(reverse('polls:book'))

    # First fetch data from POST and write to Reservation-Info
    # Order date, which is todyday
    order_date = str(datetime.datetime.now().date())
    # Total cost for this reservation
    total_cost = loop_times * int(request.POST['cost'])
    book_fee = int(total_cost*0.1)
    RI = ReservationInfo(order_date=order_date, total_cost=total_cost,
                         book_fee=book_fee, leave_date=leave_date, representative_id="Xinzhang")
    RI.save()
    # Then write to Account
    account_id, credit_card = request.POST['account_id_and_credit_card'].split(
        ",")
    user = request.user
    cus = Customer.objects.get(email=user.username)
    A = Account(customer=cus, account_id=account_id, reservation=RI,
                create_date=order_date, credit_card=credit_card)
    A.save(force_insert=True)
    # Now write to RF-Relation

    F = Flight.objects.get(fid=fid)
    RR = RfRelation(reservation=RI, fid=F, leave_date=leave_date)
    RR.save(force_insert=True)
    # Finally write to Reservation-Flight
    for i in range(loop_times):
        index = i+1
        name = str(request.POST["name"+str(index)])
        meal = request.POST["meal"+str(index)]
        cla = request.POST["class"+str(index)]
        insert_passenger_info(
            RI.reservation_id, F.fid, name, index, meal, cla, request.POST['cost'])
    return HttpResponseRedirect(reverse('polls:customer'))


@login_required(login_url='/polls/')
def customer(request):
    """For customer page"""
    template = loader.get_template('polls/customer.html')
    user = request.user
    # In original db Customer table, we use email as username to log in
    # But in Django auth.user, by default it uses only username and password to log in
    # So we first import all data in Customer table to default auth.user table
    # and set email as username
    cus = Customer.objects.get(email=user.username)
    his_query = RAW_SQL['RES_HISTORY'].format(customer_id=cus.customer_id)
    res_history = execute_custom_sql(his_query)
    cur_query = RAW_SQL['RES_CURRENT'].format(customer_id=cus.customer_id)
    res_current = execute_custom_sql(cur_query)
    context = {
        'customer': cus,
        'history': res_history,
        'current': res_current,
    }
    return HttpResponse(template.render(context, request))


@login_required(login_url='/polls/')
def manager(request):
    """For manager page"""
    template = loader.get_template('polls/manager_index.html')
    cus = Customer.objects.order_by('customer_id')
    context = {
        'customers': cus,
    }
    return HttpResponse(template.render(context, request))


def one_stop_flight(start, end, workday1, workday2):
    query = RAW_SQL['ONE_STOP_FLIGHT'].format(start_airport=start, end_airport=end, workday1=workday1,
                                              workday2=workday2)
    # print(query)
    return execute_custom_sql(query)


def exist_passenger(fid, leave_date):
    query = RAW_SQL['SEARCH_EXIST_PASSENGER'].format(
        fid=fid, leave_date=leave_date)
    return execute_custom_sql(query)


def insert_passenger_info(RID, FID, name, seat, meal, cla, price):
    query = RAW_SQL['INSERT_RES_FLIGHT'].format(
        Reservation_ID=RID, FID=FID, P_name=name, P_seat=seat, P_meal=meal, P_class=cla, Price=price)
    cursor = connection.cursor()
    cursor.execute(query)


def execute_custom_sql(s):
    cursor = connection.cursor()
    cursor.execute(s)
    return cursor.fetchall()


RAW_SQL = {
    'ONE_STOP_FLIGHT': '''
                SELECT *
                FROM(
                SELECT f1.Airline_ID as f_airline_id, f1.Flight_ID as f_flight_id, f1.Fare as f_fare, f1.Workday as f_workday,
                f1.Depart_time as f_depart_time,f1.Depart_Airport as f_depart_airport, f1.Arrive_time as f_arrive_time,
                f1.Arrive_Airport as f_arrive_airport,f2.Airline_ID as s_airline_id, f2.Flight_ID as s_flight_id, f2.Fare as s_fare,
                f2.Workday as s_worday, f2.Depart_time as s_depart_time,f2.Depart_Airport as s_depart_airport,
                f2.Arrive_time as s_arrive_time, f2.Arrive_Airport as s_arrive_airport
                FROM Flight f1
                JOIN Flight f2
                WHERE f1.Arrive_Airport=f2.Depart_Airport
                AND f1.workday={workday1} AND f2.workday={workday2}
                ) res
                WHERE f_depart_airport="{start_airport}" AND s_arrive_airport="{end_airport}"
            ''',
    'RES_HISTORY': '''
                SELECT rf.Reservation_ID, rf.FID, ri.order_date, ri.total_cost, ri.Leave_date, f.Depart_Airport, f.Arrive_Airport,
                    rf.P_name, rf.P_seat, rf.P_meal, rf.P_class, rf.Price, ri.Representative_ID
                FROM Reservation_Flight rf
                JOIN RF_Relation r on r.Reservation_ID = rf.Reservation_ID
                JOIN Reservation_Info ri on ri.Reservation_ID = rf.Reservation_ID
                JOIN Flight f on f.FID = rf.FID
                WHERE ri.order_date < '2018-01-01' AND rf.Reservation_ID in (
                    SELECT Reservation_ID
                    FROM Account a
                    WHERE a.Customer_ID = {customer_id}
                ) ORDER BY rf.Reservation_ID DESC;
            ''',
    'RES_CURRENT': '''
                SELECT rf.Reservation_ID, rf.FID, ri.order_date, ri.total_cost, ri.Leave_date, f.Depart_Airport, f.Arrive_Airport,
                    rf.P_name, rf.P_seat, rf.P_meal, rf.P_class, rf.Price, ri.Representative_ID
                FROM Reservation_Flight rf
                JOIN RF_Relation r on r.Reservation_ID = rf.Reservation_ID
                JOIN Reservation_Info ri on ri.Reservation_ID = rf.Reservation_ID
                JOIN Flight f on f.FID = rf.FID
                WHERE ri.order_date > '2018-01-01' AND rf.Reservation_ID in (
                    SELECT Reservation_ID
                    FROM Account a
                    WHERE a.Customer_ID = {customer_id}
                ) ORDER BY rf.Reservation_ID DESC;
            ''',
    'INSERT_RES_FLIGHT': '''
                INSERT INTO Reservation_Flight (Reservation_ID, FID, P_name, P_seat, P_meal, P_class, Price)
                VALUES ({Reservation_ID}, {FID}, "{P_name}", {P_seat}, "{P_meal}", "{P_class}", {Price})
            ''',
    'SEARCH_EXIST_PASSENGER': '''
                Select rf.P_name 
                from Reservation_Flight rf
                Join RF_Relation rr USING (Reservation_ID, FID)
                WHERE rr.FID={fid} and rr.leave_date = "{leave_date}";
            ''',
}


def getTomorrowDate(date):
    date = list(map(int, date.split("-")))
    date[2] = date[2] + 1
    if date[2] > 30:
        date[2] = date[2]-30
        date[1] = date[1]+1
    if date[1] > 12:
        date[1] = date[1]-12
        date[0] = date[0]+1
    result = str(date[0])+"-"
    if date[1] < 10:
        result = result + "0"
    result = result + str(date[1])+"-"
    if date[2] < 10:
        result = result + "0"
    result = result + str(date[2])
    return result


def getDayFromDate(date):
    '''
    Get day from date like 2018-03-01
    '''
    day = date.split("-")[2]
    i = int(day)
    return i

# class IndexView(generic.ListView):  # pylint: disable=too-many-ancestors
#     """
#     New function, provided by Django, easier and short code
#     """
#     template_name = 'polls/index.html'
#     context_object_name = 'latest_question_list'

#     def get_queryset(self):
#         """
#         Return the last five published questions (not including those set to be
#         published in the future).
#         """
#         return Question_new.objects.filter(pub_date__lte=timezone.now()).order_by('-pub_date')[:5]


# def detail(request, question_id):
#     '''Orignal function for detail page. Replaced by DetailView'''
#     question = get_object_or_404(Question_new, pk=question_id)
#     return render(request, 'polls/detail.html', {'question': question})
#  #      try:
#  #        question = Question_new.objects.get(pk=question_id)
#  #    except Question_new.DoesNotExist:
#  #        raise Http404("Question does not exist")
#  #    return render(request, 'polls/detail.html', {'question': question})


# class DetailView(generic.DetailView):  # pylint: disable=too-many-ancestors
#     '''
#     For detail page
#     '''
#     model = Question_new
#     template_name = 'polls/detail.html'

#     def get_queryset(self):
#         """
#         Excludes any questions that aren't published yet.
#         """
#         return Question_new.objects.filter(pub_date__lte=timezone.now())


# def results(request, question_id):
#     '''
#     Original for result page
#     '''
#     question = get_object_or_404(Question_new, pk=question_id)
#     return render(request, 'polls/results.html', {'question': question})


# class ResultsView(generic.DetailView):  # pylint: disable=too-many-ancestors
#     '''
#     For result page
#     '''
#     model = Question_new
#     template_name = 'polls/results.html'


# def vote(request, question_id):
#     '''
#     For vote page
#     '''
#     question = get_object_or_404(Question_new, pk=question_id)
#     try:
#         selected_choice = question.choice_new_set.get(
#             pk=request.POST['choice'])
#     except (KeyError, Choice_new.DoesNotExist):
#         # Redisplay the question voting form.
#         return render(request, 'polls/detail.html', {
#             'question': question,
#             'error_message': "You didn't select a Choice_new.",
#         })
#     else:
#         selected_choice.votes += 1
#         selected_choice.save()
#         # Always return an HttpResponseRedirect after successfully dealing
#         # with POST data. This prevents data from being posted twice if a
#         # user hits the Back button.
#         return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))
