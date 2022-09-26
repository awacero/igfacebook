# igfacebook
GDS service to publish seismic information using a facebook fan page account. This code was previously a plugin of EQEVENTS, but that code was modified to be used with GDS.

The files send_igfacebook.cfg and facebook_account.json must be configured before running.

GDS or the operator will decide wheter or not the information must be posted. There will be one post for the automatic (preliminar) event and another for the manual (revisado) event. If the event is older than hour_limit, there will be no publication.

**View documentation:** [igFacebook Documentation](https://awacero.github.io/igfacebook/)

## Requirements
Install the following libraries as user modules
``` bash
$ python3 -m pip install --user facebook-sdk  
$ python3 -m pip install --user ig_gds_utilities  
```
This package is required to check sqlite database from Linux bash
```bash
# apt install sqlite3 
```

## Result
If the publication works as expected, this should be posted in the facebook fan page account.

![example of a post event](./post_example.png)
