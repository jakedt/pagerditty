import csv
import logging
import sys
import argparse

from collections import namedtuple
from datetime import time, date
from functools import partial

import arrow
import intervals as I
import dateutil.tz

from pagerditty import report


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


def parse_tz(value):
    found = dateutil.tz.gettz(value)
    if found is None:
         raise argparse.ArgumentTypeError("%s is an invalid timezone" % value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument(
        '--pd_id',
        required=True,
        help='PagerDuty User ID, e.g. ABCDEFG',
    )
    parser.add_argument(
        '--pd_api_key',
        required=True,
        help='PagerDuty API key',
    )
    parser.add_argument(
        '--pd_schedule_id',
        required=True,
        action='append',
        help='PagerDuty schedule ID(s), e.g. DEFGHIJ',
    )
    parser.add_argument(
        '--slack_username',
        help='Slack username to use when determining incident engagement',
    )
    parser.add_argument(
        '--start',
        required=True,
        help='Start of the report period',
    )    
    parser.add_argument(
        '--durationunits',
        default='months',
        choices=['days', 'months', 'years'],
        help='Unit of measure for the --duration argument',
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=1,
        help='Report duration from start in --durationunits',
    )
    parser.add_argument(
        '--tz',
        default='US/Eastern',
        type=parse_tz,
        help='Time zone parseable by the datetime.tz library',
    )
    parser.add_argument(
        '--workdays',
        default='MonFri',
        choices=SCHEDULES.keys(),
        help='Days which are considered workdays',
    
    )
    parser.add_argument(
        '--day_start_hour',
        default=9,
        type=int,
        help='Working shift start time hour',
    )
    parser.add_argument(
        '--day_start_min',
        default=0,
        type=int,
        help='Working shift start time, minutes after the --day_start_hour',
    )
    parser.add_argument(
        '--day_length_hours',
        default=8,
        type=int,
        help='Duration of a working shift, in hours',
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    report.set_pagerduty_api_key(args.pd_api_key)

    since = arrow.get(args.start, tzinfo=args.tz)

    shift_kwargs = {args.durationunits: args.duration}
    until = since.shift(**shift_kwargs)

    engineer_profile = Engineer(
        args.pd_id,
        args.slack_username,
        time(args.day_start_hour, args.day_start_min),
        args.pd_schedule_id,
        args.day_length_hours,
        SCHEDULES[args.workdays],
        args.tz,
    )

    activity_intervals = generate_activity_intervals(
        since,
        until,
        engineer_profile,
    )

    print_report(activity_intervals, engineer_profile.time_zone)
