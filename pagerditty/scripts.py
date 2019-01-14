import csv
import logging
import sys

from collections import namedtuple

import intervals as I

from . import report


logger = logging.getLogger(__name__)


SCHEDULES = {
    'MonFri': I.closed(0, 4),
    'SunThu': I.closed(0, 3).union(I.closed(6,6)),
}


Engineer = namedtuple('Engineer', [
    'pagerduty_id',
    'slack_username',
    'day_start_time',
    'oncall_schedules',
    'day_length_hours',
    'workday_schedule',
    'time_zone',
])


def generate_activity_intervals(since, until, engineer):
    all_oncall = report.load_oncall(
        since,
        until,
        engineer.oncall_schedules,
        engineer.pagerduty_id,
    )
    logger.debug('Entire oncall range: %s', all_oncall)

    if all_oncall == I.empty():
        logger.debug('Engineer was not oncall during range!')
        sys.exit(0)

    work_schedule = report.generate_work_schedule(
        since,
        until,
        engineer.workday_schedule,
        engineer.day_start_time,
        engineer.day_length_hours,
    )
    logger.debug('Entire work schedule: %s', work_schedule)

    waiting_times = all_oncall.difference(work_schedule)
    logger.debug('Oncall waiting times: %s', waiting_times)

    participation_matchers = [
        report.LogParticipationMatcher('id', engineer.pagerduty_id),
    ]
    if engineer.slack_username is not None:
        participation_matchers.append(
            report.LogParticipationMatcher('name', engineer.slack_username)
        )
    incident_intervals = report.load_user_incident_intervals(
        all_oncall,
        participation_matchers,
    )
    logger.debug('Incident intervals: %s', incident_intervals)

    waiting_pay = waiting_times.difference(incident_intervals)
    incident_pay = incident_intervals.difference(work_schedule)

    return [
        report.ActivityInterval('waiting', waiting_pay),
        report.ActivityInterval('incident', incident_pay),
    ]


def print_report(activity_intervals, time_zone):
    pay_times = report.split_into_days(activity_intervals, time_zone)
    logger.debug('Final list of pay intervals: %s', pay_times)
    
    row_writer = csv.writer(sys.stdout)

    report_names = [act.name for act in activity_intervals]
    row_writer.writerow(['Date', *report_names])
    for date, hours_dict in pay_times.items():
        hours = [hours_dict[report_name] for report_name in report_names]
        row_writer.writerow([date, *hours])