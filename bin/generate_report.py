#!/usr/bin/env python

import argparse
import logging

from datetime import time

import arrow
import dateutil.tz

from pagerditty import report, scripts


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
        '--start',
        required=True,
        help='Start of the report period',
    )    
    parser.add_argument(
        '--slack_username',
        help='Slack username to use when determining incident engagement',
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
        choices=scripts.SCHEDULES.keys(),
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
    parser.add_argument(
        '--load_incidents',
        default=False,
        action='store_true',
        help='Whether to load and parse incident intervals',
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    report.set_pagerduty_api_key(args.pd_api_key)

    since = arrow.get(args.start, tzinfo=args.tz)

    shift_kwargs = {args.durationunits: args.duration}
    until = since.shift(**shift_kwargs)

    engineer_profile = scripts.Engineer(
        args.pd_id,
        args.slack_username,
        time(args.day_start_hour, args.day_start_min),
        args.pd_schedule_id,
        args.day_length_hours,
        scripts.SCHEDULES[args.workdays],
        args.tz,
    )

    activity_intervals = scripts.generate_activity_intervals(
        since,
        until,
        engineer_profile,
        args.load_incidents,
    )

    scripts.print_report(activity_intervals, engineer_profile.time_zone)
