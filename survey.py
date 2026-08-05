#!/usr/bin/env python3
"""Field survey toolkit: convert MapPro exports, solve the gNB, render the story.

Usage:
    python survey.py                          interactive picker
    python survey.py 20260716                 pick a verb for one survey
    python survey.py 20260716 convert         MapPro exports -> My Maps CSV
    python survey.py 20260716 solve           trilaterate the gNB
    python survey.py 20260716 animate         render the animation
    python survey.py --list                   what each survey can do
    python survey.py convert FILE.csv...      convert files by path
    python survey.py solve SURVEY.csv BINOC.xlsx

Surveys are discovered under --data-root, which defaults to this project's
data/raw/. A survey needs only a MapPro export to be discovered; solving also
needs its <name>*.xlsx sightings workbook, and animating needs manimgl.
"""

from __future__ import annotations

from gnb_survey.cli.dispatch import cli_entry

if __name__ == "__main__":
    cli_entry()
