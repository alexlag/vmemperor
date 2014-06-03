from flask import Flask
from flask import session as flask_session
from flask import render_template
from functools import wraps
from flask import request, Response, redirect, url_for, abort

import XenAPI
import pprint
import random
import string
import time
from getvminfo import get_vms_list
from gettemplateinfo import get_template_list


app = Flask(__name__)


def get_xen_session(endpoint):
    url = endpoint['url']
    print url
    session = XenAPI.Session(url)
    session.login_with_password((flask_session[url])['login'], (flask_session[url])['password'])
    return session


def retrieve_vms_list(endpoint):
    session = get_xen_session(endpoint)
    api = session.xenapi
    pool_master = ""
    for pool in api.pool.get_all():
        pool_master = api.pool.get_master(pool)

        for host in api.host.get_all():
            host_name_label = api.host.get_name_label(host)
            free_mem = int(api.host.compute_free_memory(host))/(1024*1024)

    vm_list = get_vms_list(session, endpoint)
    vm_list = sorted(vm_list, key=lambda k: (k['power_state'].lower(), k['name_label'].lower()))
    return vm_list


def retrieve_template_list(endpoint):
    session = get_xen_session(endpoint)
    api = session.xenapi
    template_list = get_template_list(session, endpoint)
    return template_list



# VM_metrics.get_all()
# VM_metrics.get_start_time()
# VM_metrics.get_os_version()
# VM_metrics.get_install_time()
# VM_metrics.get_memory_actual()
# VM_metrics.get_VCPU/utilisation() #map int->float
# VM_metrics.get_state()

def check_auth(username, password, session):
    # First acquire a valid session by logging in:
    try:
        session.xenapi.login_with_password(username, password)
        if 'Status' in session:
            print session
            if session['Status'] == 'Failure':
                return False
        return True
    except:
        return False


def check_if_superuser(session):
    try:
        is_a_superuser = session.xenapi.session.get_is_local_superuser(session._session)
        print ("Is a superuser?", is_a_superuser)
        return is_a_superuser
    except:
        return False


@app.route("/auth", methods=['GET', 'POST'])
def authenticate():
    """Sends a 401 response that enables basic auth"""
    if request.method == 'GET':
        return render_template("auth.html", xen_endpoints=app.config['xen_endpoints'])
    if request.method == 'POST':
        counter = 0
        is_su = True
        for endpoint in app.config['xen_endpoints']:
            login = request.form['login' + str(counter)]
            password = request.form['password' + str(counter)]
            session = XenAPI.Session(endpoint['url'])
            if check_auth(login, password, session):
                flask_session[endpoint['url']] = {'url': endpoint['url'], 'login': login, 'password': password}
                print "Auth successful"
                is_su = check_if_superuser(session) and is_su
                print is_su
                #print flask_session[endpoint]['url']
            else:
                print "FAILED TO AUTH ON " + endpoint['description']
        flask_session['is_su'] = is_su

        return redirect("/")


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        for endpoint in app.config['xen_endpoints']:
            if endpoint['url'] in flask_session:
                if not flask_session[endpoint['url']]['url'] \
                        or not flask_session[endpoint['url']]['login'] \
                        or not flask_session[endpoint['url']]['password']:
                    return redirect(url_for('authenticate'))
            else:
                print ("Missing auth info for ", endpoint)
                return redirect(url_for('authenticate'))

        return f(*args, **kwargs)
    return decorated


@app.route('/listvms')
@requires_auth
def list_vms():
    vm_list = []
    for endpoint in app.config['xen_endpoints']:
        vm_list.extend(retrieve_vms_list(endpoint))
    vm_list = sorted(vm_list, key=lambda k: (k['power_state'].lower(), k['name_label'].lower()))
    return render_template('vms.html', vm_list=vm_list)

@app.route('/listtemplates')
@requires_auth
def list_templates():
    template_list = []
    if 'is_su' in flask_session and flask_session['is_su']:
        for endpoint in app.config['xen_endpoints']:
            template_list.extend(retrieve_template_list(endpoint))
        template_list = sorted(template_list, key=lambda k: (k['name_label'].lower(), -len(k['tags'])))
    return render_template('vm_templates.html', template_list=template_list)


@app.route('/')
@requires_auth
def secret_page():
    return render_template('index.html')



@app.route('/startvm', methods=['POST'])
@requires_auth
def start_vm():
    vm_uuid = request.form.get('vm_uuid')
    endpoint_url = request.form.get('endpoint_url')
    endpoint_description = request.form.get('endpoint_description')
    if not vm_uuid or not endpoint_url or not endpoint_description:
        abort(406, "Not acceptible: syntax error in your query")

    endpoint = {'url': endpoint_url, 'description': endpoint_description}
    session = get_xen_session(endpoint)
    api = session.xenapi
    vm_ref = api.VM.get_by_uuid(vm_uuid)
    try:
        vm = api.VM.get_record(vm_ref)
        api.VM.start(vm_ref, False, False)
        return "Success!"
    except:
        abort(500, "Couldn't start VM, reason unknown")


#app.secret_key = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
app.secret_key = 'SADFccadaeqw221fdssdvxccvsdf'
if __name__ == '__main__':
    #app.config.update(SESSION_COOKIE_SECURE=True)
    app.config['xen_endpoints'] = [{'url': 'https://172.31.0.10:443/', 'description': 'Pool A'},
                                   {'url': 'https://172.31.0.30:443/', 'description': 'Pool Z'}]
    #retrieve_vms_list(session)
    app.run(debug=True)