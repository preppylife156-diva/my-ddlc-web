# Copy this file into the selected Ren'Py game's game/ directory.
<<<<<<< HEAD
# This patch is compatible with the bundled Ren'Py 6.99/Python 2.7 runtime.

init -10 python:
    import json
    import os
=======
# Scene targets are checked against the labels exposed by the running game.

init -10 python:
    import json
>>>>>>> origin/main

    try:
        import urllib.request as ddlc_cc_url
    except ImportError:
        import urllib2 as ddlc_cc_url

    try:
        ddlc_cc_string_types = (basestring,)
    except NameError:
        ddlc_cc_string_types = (str,)

<<<<<<< HEAD
    ddlc_cc_token_path = os.environ.get(
        "DDLC_CC_TOKEN_FILE",
        os.path.expanduser("~/.ddlc-control-centre-token"),
    )
    ddlc_cc_token = ""
    try:
        with open(ddlc_cc_token_path, "rb") as ddlc_cc_token_file:
            ddlc_cc_token = ddlc_cc_token_file.read().strip().decode("ascii")
    except Exception:
        pass

=======
    ddlc_cc_token = "ddlc-control-centre-local-v1"
>>>>>>> origin/main
    ddlc_cc_connection_status = "Waiting for bridge"
    ddlc_cc_last_scene = "(none)"
    ddlc_cc_polling = False
    ddlc_cc_act_targets = {
        "1": "ch0_main",
        "2": "ch21_main",
        "3": "ch30_main",
        "4": "ch40_main",
    }

    def ddlc_cc_request(path, payload=None):
<<<<<<< HEAD
        if not ddlc_cc_token:
            raise IOError("Control Centre bridge token file is unavailable")
=======
>>>>>>> origin/main
        url = "http://127.0.0.1:8765" + path + "?token=" + ddlc_cc_token
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = ddlc_cc_url.Request(url, data=body)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        response = ddlc_cc_url.urlopen(request, timeout=0.5)
        return json.loads(response.read())

<<<<<<< HEAD
    def ddlc_cc_report(message, ok=True, scene=None, labels=None):
        try:
            payload = {
                "message": str(message)[:900],
                "ok": bool(ok),
                "scene": scene,
            }
            if labels is not None:
                payload["labels"] = labels
            ddlc_cc_request("/result", payload)
=======
    def ddlc_cc_report(message, ok=True, scene=None):
        try:
            ddlc_cc_request("/result", {
                "message": str(message)[:900],
                "ok": bool(ok),
                "scene": scene,
            })
>>>>>>> origin/main
        except Exception:
            pass

    def ddlc_cc_scene_labels():
        return sorted([
            label for label in renpy.get_all_labels()
            if isinstance(label, ddlc_cc_string_types)
        ])

    def ddlc_cc_poll_once():
        global ddlc_cc_connection_status, ddlc_cc_last_scene, ddlc_cc_polling
        if ddlc_cc_polling:
            return
        ddlc_cc_polling = True
<<<<<<< HEAD
        jump_target = None
        restart_game = False
=======
>>>>>>> origin/main
        try:
            response = ddlc_cc_request("/poll")
            ddlc_cc_connection_status = "Connected"
            item = response.get("command")
            if not item:
                return
            command = str(item.get("command", "")).strip()
            parts = command.split(None, 1)
            if not parts:
                ddlc_cc_report("Empty command received.", False)
                return
            name = parts[0].lower()
            argument = parts[1].strip() if len(parts) > 1 else ""

            if command == "scene list":
                labels = ddlc_cc_scene_labels()
<<<<<<< HEAD
                ddlc_cc_report("Runtime reports %d scene labels." % len(labels), True, labels=labels)
=======
                ddlc_cc_report("Runtime labels:\n" + "\n".join(labels[:60]), True)
>>>>>>> origin/main
            elif command == "scene current":
                ddlc_cc_report("Last requested label: " + ddlc_cc_last_scene, True, ddlc_cc_last_scene)
            elif name == "scene":
                if not argument or len(argument) > 120 or not renpy.has_label(argument):
                    ddlc_cc_report("Unknown label. Use scene list for labels in this running game.", False)
                else:
                    ddlc_cc_last_scene = argument
                    ddlc_cc_report("Jumping to runtime-verified label: " + argument, True, argument)
<<<<<<< HEAD
                    jump_target = argument
=======
                    renpy.jump(argument)
>>>>>>> origin/main
            elif name == "act" and argument in ddlc_cc_act_targets:
                target = ddlc_cc_act_targets[argument]
                if not renpy.has_label(target):
                    ddlc_cc_report("Act " + argument + " is unavailable: label " + target + " was not found by this game runtime.", False)
                else:
                    ddlc_cc_last_scene = target
                    ddlc_cc_report("Jumping to runtime-verified Act " + argument + " label: " + target, True, target)
<<<<<<< HEAD
                    jump_target = target
            elif command in ("reset", "restart-game"):
                ddlc_cc_report("Restarting the game through Ren'Py.", True)
                restart_game = True
=======
                    renpy.jump(target)
            elif command in ("reset", "restart-game"):
                ddlc_cc_report("Restarting the game through Ren'Py.", True)
                renpy.full_restart()
>>>>>>> origin/main
            else:
                ddlc_cc_report("Unsupported game command.", False)
        except Exception as error:
            ddlc_cc_connection_status = "Bridge unavailable: " + str(error)[:120]
        finally:
            ddlc_cc_polling = False

<<<<<<< HEAD
        if jump_target is not None:
            renpy.jump(jump_target)
        elif restart_game:
            renpy.full_restart()

=======
>>>>>>> origin/main
screen ddlc_cc_bridge_overlay():
    zorder 100
    draggroup:
        drag:
            drag_name "ddlc_cc_control_button"
            draggable True
            xpos 0.94
            ypos 0.08
            child:
                textbutton "CC" action ToggleScreen("ddlc_cc_status_overlay")
    timer 1.0 repeat True action Function(ddlc_cc_poll_once)

screen ddlc_cc_status_overlay():
    zorder 101
    frame:
        xalign 0.5
        yalign 0.5
        padding (18, 14)
        vbox:
            spacing 8
            text "DDLC Control Centre"
            text "Bridge: [ddlc_cc_connection_status]"
            textbutton "Close" action Hide("ddlc_cc_status_overlay")

init -10 python:
    if "ddlc_cc_bridge_overlay" not in config.overlay_screens:
        config.overlay_screens.append("ddlc_cc_bridge_overlay")
