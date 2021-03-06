from __future__ import absolute_import
import os
import requests
import celeryconfig
import json
from os import path, environ

from flask import Flask, jsonify, render_template, request
from celery import Celery
from utils import map_answers

app = Flask(__name__)
app.config.from_object(celeryconfig)


def make_celery(app):
    """
    Function to run celery alongside Flask. It ties the configuration of
    Celery and Flask together. Then they can be used together very easily.
    """
    celery = Celery(
        'overlord',
        broker='amqp://guest:guest@localhost//',
        backend='amqp',
        include=["backup", "server", "static", "feedback", "reminder", "orgsyncattendance", 'orgsync'],
    )
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery


@app.route("/")
def home_page():
    """
    Renders the homepage
    """
    return render_template('index.html')


@app.route("/<userId>/json")
def get_JSON(userId):
    """
    Gets the userId of the person currently logged in and verifies if the
    person in question is a TEAM_MEMBER. This is done because any individual
    can run any task. Mostly because of security through obscurity.
    """

    # Makes a call to the API to verify the person
    headers = {
        'content-type': 'application/vnd.api+json',
        'accept': 'application/*, text/*',
        'x-api-key': os.environ['TNYU_API_KEY']
    }
    person = requests.get('https://api.tnyu.org/v2/people/' +
                          userId, headers=headers, verify=False)

    # The person is not logged in
    if person.status_code is not 200:
        return jsonify({'status': '401'})

    # Authentication is successful
    if len(person.json()['data']['attributes']['roles']) > 0:
        # Throws a JSON object that contains all of the tasks that
        # the users can run.
        return jsonify({
            'flower': 'http://overlord.tnyu.org:5555/',
            'static': [
                {
                    'name': 'trigger_build',
                    'parameters': ['repository', 'branch'],
                    'path': '/task/static/trigger_build/<repository>/<branch>',
                    'result': '/result/static/trigger_build/<task_id>',
                }
            ],
            'server': [
                {
                    'name': 'monitor_services',
                    'parameters': [],
                    'path': '/task/server/monitor_services',
                    'result': '/result/server/monitor_services/<task_id>',
                },
                {
                    'name': 'monitor_techatnyu_org',
                    'parameters': [],
                    'path': '/task/server/monitor_techatnyu_org',
                    'result': '/result/server/monitor_techatnyu_org/<task_id>',
                }
            ],
            'backup': [
                {
                    'name': 'backup_bd_mysql',
                    'parameters': [],
                    'path': '/task/backup/backup_bd_mysql',
                    'result': '/result/backup/backup_bd_mysql/<task_id>',
                },
                {
                    'name': 'backup_mongo',
                    'parameters': [],
                    'path': '/task/backup/backup_mongo',
                    'result': '/result/backup/backup_mongo/<task_id>',
                },
                {
                    'name': 'backup_jira',
                    'parameters': [],
                    'path': '/task/backup/backup_jira',
                    'result': '/result/backup/backup_jira/<task_id>',
                },
                {
                    'name': 'backup_discuss',
                    'parameters': [],
                    'path': '/task/backup/backup_discuss',
                    'result': '/result/backup/backup_discuss/<task_id>',
                },
                {
                    'name': 'backup_maltrain_mysql',
                    'parameters': [],
                    'path': '/task/backup/backup_mailtrain_sql',
                    'result': '/result/backup/backup_mailtrain_sql/<task_id>',
                }
            ]
        })
    # jsonify will do for us all the work, returning the
    # previous data structure in JSON
    return jsonify({'status': '401'})


@app.route("/task/static/<task>/<repository>/<branch>")
def static_web(task, repository, branch):
    """
    Adheres to running all of the tasks in the static.py file:
    Runs a particular task that the user provides
    """
    if task == 'trigger_build':
        from static import trigger_build
        res = trigger_build.apply_async([repository, branch])
        context = {"id": res.task_id,
                   "repository": repository, "branch": branch}
        result = "trigger_build({repository}, {branch})".format(
            context['repository'], context['branch'])
        goto = "{}".format(context['id'])
        return jsonify(result=result, goto=goto)

    return jsonify({"Error": "Wrong Task"})


@app.route("/result/static/<task>/<task_id>")
def static_web_result(task, task_id):
    """
    Adheres to running all of the tasks in the static.py file:
    Static Result for running a particular task
    """
    if task == 'trigger_build':
        from static import trigger_build
        retval = trigger_build.AsyncResult(task_id).get(timeout=1.0)
        return repr(retval)

    return jsonify({"Error": "Wrong Task"})


@app.route("/task/server/<task>")
def server_web(task):
    """
    Adheres to running all of the tasks in the server.py file:
    Runs a particular task that the user provides.
    """
    if task == 'monitor_services':
        from server import monitor_services
        res = monitor_services.apply_async([])

    if task == 'monitor_techatnyu_org':
        from server import monitor_techatnyu_org
        res = monitor_techatnyu_org.apply_async([])

    return jsonify({"Error": "Wrong Task"})


@app.route("/result/server/<task>/<task_id>")
def server_web_result(task, task_id):
    """
    Adheres to results of all the tasks in the server.py file:
    Server Result for running a particular task.
    """
    if task == 'monitor_services':
        from server import monitor_services
        retval = monitor_services.AsyncResult(task_id).get(timeout=1.0)
        return repr(retval)

    if task == 'monitor_techatnyu_org':
        from server import monitor_techatnyu_org
        retval = monitor_techatnyu_org.AsyncResult(
            task_id).get(timeout=1.0)
        return repr(retval)

    return jsonify({"Error": "Wrong Task ID"})


@app.route("/task/backup/<task>")
def backup_web(task):
    """
    Adheres to running all of the tasks in the backup.py file:
    Runs a particular task that the user provides.
    """
    if task == 'backup_mongo':
        from backup import backup_mongo
        res = backup_mongo.apply_async([])
        result = "backup_mongo()"

    if task == 'backup_jira':
        from backup import backup_jira
        res = backup_jira.apply_async([])
        result = "backup_jira()"

    if task == 'backup_discuss':
        from backup import backup_discuss
        res = backup_discuss.apply_async([])
        result = "backup_discuss()"

    if task == 'backup_mailtrain_sql':
        from backup import backup_mailtrain_sql
        res = backup_mailtrain_sql.apply_async([])
        result = "backup_mailtrain_sql()"

    return jsonify({"Error": "Wrong Task"})


@app.route("/result/backup/<task>/<task_id>")
def backup_web_result(task, task_id):
    """
    Adheres to results of all the tasks in the backup.py file:
    Backup Result for running a particular task.
    """
    if task == 'backup_mongo':
        from backup import backup_mongo
        retval = backup_mongo.AsyncResult(task_id).get(timeout=1.0)
        return repr(retval)

    if task == 'backup_jira':
        from backup import backup_jira
        retval = backup_jira.AsyncResult(task_id).get(timeout=1.0)
        return repr(retval)

    if task == 'backup_discuss':
        from backup import backup_discuss
        retval = backup_discuss.AsyncResult(task_id).get(timeout=1.0)
        return repr(retval)

    if task == 'backup_mailtrain_sql':
        from backup import backup_mailtrain_sql
        retval = backup_mailtrain_sql.AsyncResult(task_id).get(timeout=1.0)
        return repr(retval)

    return jsonify({"Error": "Wrong Task"})


@app.route('/typeform_webhook', methods=['POST'])
def typeform():
    """
    Webhook for typeform feedback form.
    """
    json_res = json.loads(request.data)
    res = requests.get('https://api.typeform.io/v0.4/forms/jM87mkTPhb', headers=headers)
    form_schema = res.json()

    print map_answers(json_res, form_schema)

    return jsonify({"Status": "Success"})

@app.errorhandler(404)
def error(e):
    return jsonify({'status': 404})

celery = make_celery(app)

if __name__ == "__main__":
    port = int(environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
