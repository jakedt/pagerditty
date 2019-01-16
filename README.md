# PagerDitty

Simple script I threw together to generate oncall waiting and working time reports for my team of SREs.

## TODO

- Make this a webapp so we can run it with the `pd_api_key` baked in
- Find an easy way to feed it a holiday schedule

## Example usage

```console
foo@bar:~$ docker run -it quay.io/jakedt/pagerditty --pd_api_key y_NbAkKc66ryYTWUXYEu --pd_id PBPDVGQ --pd_schedule_id P538IZH --start 2018-12-01T00:00:00Z
Date,waiting,incident
2018-12-02,12.0,0
2018-12-03,7.0,0
2018-12-04,7.0,0
2018-12-05,7.0,0
2018-12-06,7.0,0
2018-12-07,7.0,0
2018-12-08,12.0,0
2018-12-16,12.0,0
2018-12-17,7.0,0
2018-12-18,7.0,0
2018-12-19,7.0,0
2018-12-20,7.0,0
2018-12-21,7.0,0
2018-12-22,12.0,0
2018-12-30,12.0,0
2018-12-31,7.0,0
```
