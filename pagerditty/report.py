import logging

from collections import defaultdict, namedtuple
from datetime import datetime

import arrow
import intervals as I
import pypd

logger = logging.getLogger(name=__name__)


LogParticipationMatcher = namedtuple('LogParticipationMatcher', [
    'logentry_field',
    'field_match_value',
])


ActivityInterval = namedtuple('ActivityInterval', [
    'name',
    'intervals',
])


def __pd_parse_time(time_str):
    return arrow.get(time_str)


def __times_to_interval(start, end):
    assert end > start
    return I.closed(start.timestamp, end.timestamp)


def set_pagerduty_api_key(api_key):
    pypd.api_key = api_key


def load_oncall(since, until, schedule_id_list, user_id):
    oncall = I.empty()

    for schedule_id in schedule_id_list:
        schedule = pypd.Schedule.fetch(
            id=schedule_id,
            since=since,
            until=until,
            time_zone='UTC',
        )

        entries = schedule['final_schedule']['rendered_schedule_entries']
        for rendered_entry in entries:
            rendered_user_id = rendered_entry['user']['id']
            if rendered_user_id != user_id:
                logger.debug('Skipping user id: %s', rendered_user_id)
                continue

            oncall_start = __pd_parse_time(rendered_entry['start'])
            oncall_end = __pd_parse_time(rendered_entry['end'])

            logger.debug('Found oncall: %s - %s', oncall_start, oncall_end)
            
            oncall = oncall.union(__times_to_interval(oncall_start, oncall_end))

    return oncall


def generate_work_schedule(since, until, workdays, workday_start_time,
                           hours_per_day):
    work_schedule = I.empty()

    for day_start, day_end in arrow.Arrow.span_range('day', since, until):
        if workdays.contains(day_start.weekday()):
            logger.debug('%s is a workday', day_start)

            workday_start = arrow.Arrow.fromdatetime(
                datetime.combine(
                    day_start.datetime.date(),
                    workday_start_time,
                ),
                day_start.tzinfo,
            )
            workday_end = workday_start.shift(hours=hours_per_day)
            logger.debug('Workday times: %s - %s', workday_start, workday_end)

            workday_interval = __times_to_interval(workday_start, workday_end)
            work_schedule = work_schedule.union(workday_interval)

    return work_schedule    


def split_into_days(activity_intervals, tz):
    start = I.inf
    end = -I.inf

    for _, intervals in activity_intervals:
        start = min(start, intervals.lower)
        end = max(end, intervals.upper)

    midnights = I.empty()
    day_span_range = arrow.Arrow.span_range(
        'day',
        arrow.get(start),
        arrow.get(end),
        tz=tz,
    )
    for midnight, _ in day_span_range:
        midnights = midnights.union(
            I.closed(midnight.timestamp, midnight.timestamp)
        )

    logger.debug('Midnights: %s', midnights)

    hours_per_day = defaultdict(lambda: defaultdict(int))
    for report_name, intervals in activity_intervals:
        if intervals == I.empty():
            continue

        pay_interval_by_day = intervals.difference(midnights)
        for day_interval in pay_interval_by_day:
            logger.debug(
                'Day interval[%s]: %s - %s',
                report_name,
                day_interval.lower,
                day_interval.upper,
            )
            total_seconds = day_interval.upper - day_interval.lower
            interval_date = datetime.fromtimestamp(day_interval.lower).date()
            hours_per_day[interval_date][report_name] += total_seconds/3600

    return hours_per_day


def __user_participated_at_timestamp(incident, participation_matchers):
    logger.debug('Candidate incident: %s', incident['id'])
    started_participating_at = I.inf
    for logentry in incident.log_entries(is_overview=True):
        agent = logentry['agent']

        for matcher in participation_matchers:
            found_field_value = agent.get(matcher.logentry_field, None)
            if found_field_value == matcher.field_match_value:
                participation_time = __pd_parse_time(logentry['created_at'])
                started_participating_at = min(started_participating_at,
                                               participation_time.timestamp)
                break

    return started_participating_at


def load_user_incident_intervals(all_oncall, participation_matchers):
    assert all_oncall != I.empty()
    since = arrow.get(all_oncall.lower)
    until = arrow.get(all_oncall.upper)

    incident_intervals = I.empty()
    
    for incident in pypd.Incident.find(since=since, until=until):
        # Make sure that the start time of the incident is in a waiting window
        incident_start = __pd_parse_time(incident['created_at']).timestamp
        if all_oncall.contains(incident_start):
            # Add this incident interval to the list of incident work times
            participation_start = __user_participated_at_timestamp(
                incident,
                participation_matchers,
            )

            incident_end = __pd_parse_time(
                incident['last_status_change_at']
            ).timestamp

            participation_ival = I.closed(participation_start, incident_end)
            incident_intervals = incident_intervals.union(participation_ival)

            if participation_start < I.inf:
                logger.debug(
                    'User participated in incident %s from %s - %s',
                    incident['id'],
                    participation_start,
                    incident_end
                )
            
    return incident_intervals
