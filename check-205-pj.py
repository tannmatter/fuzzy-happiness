#!/usr/bin/python3

if __name__ == "__main__":

    import os
    from datetime import datetime

    from sendmail import send_mail
    from drivers.projector.nec import NEC

    pj_ip = '161.31.108.31'
    pj_port = 7142
    time = datetime.now()
    room = 'Burdick 205'
    pj_on = "The time is {0}.  The projector in {1} is currently running.  It "\
            "may have been left on unintentionally, or there may be a group "\
            "still using the room right now.".format(time, room)
    pj_off= "The projector in {0} is turned off.".format(room)
    snapshot_script = '/home/mtanner/src/python/avcontrols/curl-snapshot.sh'

    my_projector = NEC(comm_method='tcp', ip_address=pj_ip, port=pj_port)
    result = my_projector.power_status
    if result is not None:
        power_status = result.casefold()
        if "power on" in power_status:
            print(pj_on)
            # curl a snapshot
            script = os.popen(snapshot_script)
            imgfile = script.read().rstrip()
            send_mail(
                subject=room+" projector is on!", body=pj_on,
                send_to=['avservices@uca.edu'], files=[imgfile]
            )
            os.system('rm '+imgfile)
        elif "standby" in power_status:
            print(pj_off)
        elif "cooling" in power_status:
            print("The projector is currently shutting down and cooling off.")
        else:
            print("Status unknown")
