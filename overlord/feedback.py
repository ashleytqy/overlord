import os
import requests

from datetime import datetime
from dateutil.parser import parse
from pytz import timezone

from threading import Thread
from overlord import celery
from utils import Event, Email, headers


class FeedBackEmail(Email):

    def _generate_emails(self, members):
        for i, member in enumerate(members):
            msg = "\r\n".join([
                "From: Tech@NYU Feedback <" + os.environ['TNYU_EMAIL'] + ">",
                "To: " + members[i]['attributes']['contact']['email'],
                "Subject: Thank you for coming to Tech@NYU's " +
                self.event_data[0]['attributes']['title'],
                '',
                'Hi ' + members[i]['attributes']['name'] + '!\n\n' +
                'Thanks for coming out! We are constantly looking to improve ' +
                'on our events, and we would really appreciate it if you ' +
                'could take two minutes out of your day to fill out our ' +
                'feedback form. We\'d love to know how we could do better: ' +
                self.typeform_link,
                '',
                'Filling the form out will give us an idea of how everything ' +
                'went and if there was something you really liked about the ' +
                'event or something you did not like.\n',
                'Feel free to email feedback@techatnyu.org if you have ' +
                'other questions or concerns.',
                '',
                'Thank you,',
                'Tech@NYU team'
            ])

            try:
                err = self.server.sendmail(os.environ['TNYU_EMAIL'], members[i][
                    'attributes']['contact']['email'], msg)
                if err:
                    print(err)
            except UnicodeEncodeError:
                continue

    @property
    def typeform_link(self):
        return "https://techatnyu.typeform.com/to/hEHu5Z"

    def send_emails(self, event_id):
        self._get_emails(event_id)
        self._generate_emails(self.eboard_members)
        self._generate_emails(self.attendees)


def get_resource():
    root_url = "https://api.tnyu.org/v3/events/"
    r = requests.get(root_url + "?sort=-endDateTime", headers=headers)
    return r.json()


def get_events_ended_today():
    resources = get_resource()['data']
    events = [Event(x) for x in resources]

    # Change timezone to UTC
    today = timezone("America/New_York").localize(datetime.today())
    today_events = []

    for event in events:

        event_date = parse(event.endDateTime).astimezone(timezone("America/New_York"))

        # Break the loop if an event in the past is detected
        if event_date.date() < today.date():
            break

        # Check if an event ended today
        if event_date.date() == today.date() and event_date < today:
            today_events.append(event)

    return today_events


@celery.task
def send_emails():
    emails = FeedBackEmail()
    events = get_events_ended_today()

    for event in events:
        thr = Thread(target=emails.send_emails, args=[event.id])
        thr.start()

    return True
