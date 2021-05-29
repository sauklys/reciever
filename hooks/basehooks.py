from time import time
from json import dumps
from requests import post
from threading import Thread
from reciever import get_server_config


def poll_server_async(event):
    config = get_server_config()
    callback_target = config["mod"]["callback_target"]
    if callback_target is not None:
        got = post(callback_target, json=event)


def get_slot_by_name(name, all_vehicles):
    for vehicle in all_vehicles["vehicles"]:
        if vehicle["driverName"] == name:
            return vehicle["slotID"]
    return None


def get_last_lap_time(name, all_vehicles):
    for vehicle in all_vehicles["vehicles"]:
        if vehicle["driverName"] == name:
            return vehicle["lastLapTime"]
    return None


def poll_server(event):
    background_thread = Thread(target=poll_server_async, args=(event,), daemon=True)
    background_thread.start()


def best_lap(driver, time, team, newStatus):
    print("New best lap {}: {}".format(driver, time))


def new_lap(driver, laps, newStatus):
    print("New lap count {}: {}".format(driver, laps))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    last_lap_time = get_last_lap_time(driver, newStatus)
    poll_server(
        {
            "driver": driver,
            "laps": laps,
            "type": "LC",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
            "last_lap_time": last_lap_time,
        }
    )


def on_pos_change(driver, old_pos, new_pos, newStatus):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "driver": driver,
            "old_pos": old_pos,
            "new_pos": new_pos,
            "type": "P",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def on_pos_change_yellow(driver, old_pos, new_pos, newStatus):
    print("New position for {}: {} (was {}) ".format(driver, new_pos, old_pos))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "driver": driver,
            "old_pos": old_pos,
            "new_post": new_pos,
            "type": "PY",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def test_lag(driver, speed, old_speed, location, nearby, team, additional, newStatus):
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    print(
        "Suspected lag for {} v={}, v_old={}, l={}, nearby={}".format(
            driver, speed, old_speed, location, nearby
        )
    )
    poll_server(
        {
            "driver": driver,
            "speed": speed,
            "old_speed": old_speed,
            "location": location,
            "nearby": nearby,
            "team": team,
            "type": "L",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def add_penalty(driver, old_penalty_count, penalty_count, newStatus):
    print("A penalty was added for {}. Sum={}".format(driver, penalty_count))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "sum": penalty_count,
            "driver": driver,
            "type": "P+",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def revoke_penalty(driver, old_penalty_count, penalty_count, newStatus):
    print("A penalty was removed for {}. Sum={}".format(driver, penalty_count))
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "sum": penalty_count,
            "driver": driver,
            "type": "P-",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def personal_best(driver, old_best, new_best, newStatus):
    print(
        "A personal best was set: {} old={}, new={}".format(driver, old_best, new_best)
    )
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "new_best": new_best,
            "old_best": old_best,
            "driver": driver,
            "type": "PB",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def on_pit_change(driver, old_status, status, newStatus):
    print(
        "Pit status change for {} is now {}, was {}".format(driver, status, old_status)
    )
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    if status != "REQUEST":  # request is a bit too leaky for the public
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "PS",
                "event_time": event_time,
                "session": session,
                "slot_id": get_slot_by_name(driver, newStatus),
            }
        )


def on_garage_toggle(driver, old_status, status, newStatus):
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    if status:
        print("{} is now exiting the garage".format(driver))
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "GO",
                "event_time": event_time,
                "session": session,
                "slot_id": get_slot_by_name(driver, newStatus),
            }
        )
    else:
        print("{} returned to the garage".format(driver))
        poll_server(
            {
                "old_status": old_status,
                "status": status,
                "driver": driver,
                "type": "GI",
                "event_time": event_time,
                "session": session,
                "slot_id": get_slot_by_name(driver, newStatus),
            }
        )


pit_times = {}


def on_pitting(driver, old_status, status, newStatus):
    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    if status:
        pit_times[driver] = time()
        print("{} is now pitting".format(driver))
        poll_server(
            {
                "driver": driver,
                "type": "PSS",
                "event_time": event_time,
                "session": session,
                "slot_id": get_slot_by_name(driver, newStatus),
            }
        )

    else:
        try:
            start_time = pit_times[driver] if driver in pit_times else 0
            if start_time > 0:
                duration = time() - start_time
                print(
                    "{} finished pitting. Pit took {} seconds.".format(driver, duration)
                )
                poll_server(
                    {
                        "driver": driver,
                        "type": "PSE",
                        "event_time": event_time,
                        "session": session,
                        "slot_id": get_slot_by_name(driver, newStatus),
                    }
                )
            else:
                print("{} finished pitting".format(driver))
                poll_server(
                    {
                        "driver": driver,
                        "type": "PSE",
                        "event_time": event_time,
                        "session": session,
                        "slot_id": get_slot_by_name(driver, newStatus),
                    }
                )
        except:
            import traceback

            print(traceback.print_exc())


def status_change(driver, old_status, new_status, newStatus):
    print(
        "Finish status change for {} is now {}, was {}".format(
            driver, new_status, old_status
        )
    )

    event_time = newStatus["currentEventTime"]
    session = newStatus["session"]
    poll_server(
        {
            "driver": driver,
            "old_status": old_status,
            "status": new_status,
            "type": "S",
            "event_time": event_time,
            "session": session,
            "slot_id": get_slot_by_name(driver, newStatus),
        }
    )


def on_flag_change(driver, old_flag, new_flag, newStatus):
    print(
        "Driver {} sees a flag change to {} (was {})".format(driver, new_flag, old_flag)
    )
