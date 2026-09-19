"""Source health: what a green light is allowed to mean.

Two properties are worth a test, because both are ways a console can mislead an operator without
saying anything false:

- a source that cannot produce a verdict must never report a liveness state, so reference material
  and demodulated third-party frames never sit under the same indicator as a receiver;
- ONLINE must require a recent observation, not merely a service that answers, so there is no
  indicator that is permanently green because nothing ever changes it.
"""

import datetime as dt
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import sources                                     # noqa: E402


def _ago(seconds):
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds)
    return when.isoformat(timespec='seconds').replace('+00:00', 'Z')


class Feed(sources.SignalSource):
    """A stub ENGINE source with a one-hour freshness window and a settable last observation."""

    key, name, operator = 'stub_feed', 'Stub feed', 'Test'
    feeds = sources.ENGINE
    freshness_s = 3600

    def __init__(self, reachable=sources.ONLINE, last=None):
        self._reachable, self._last = reachable, last

    def check(self, timeout=8):
        return self._reachable, 'stub'

    def last_data_utc(self):
        return self._last


def test_every_state_the_registry_reports_is_in_the_published_vocabulary():
    for s in sources.status_all(include_network=False):
        assert s['health']['state'] in sources.HEALTH_STATES, s
        assert s['health']['reachable'] in sources.HEALTH_STATES, s
        assert s['feeds'] in (sources.ENGINE, sources.REFERENCE_ONLY, sources.METADATA_ONLY)


def test_a_source_that_cannot_produce_a_verdict_never_reports_a_liveness_state():
    """Published specifications and third-party demodulated frames are reachable all day. Calling
    either ONLINE would put the same green dot beside documentation as beside a receiver."""
    for src in sources.SOURCES:
        if src.feeds == sources.ENGINE:
            continue
        assert src.health_state(sources.ONLINE, age_s=0) == src.feeds
        assert src.health_state(sources.OFFLINE, age_s=None) == src.feeds
    kinds = {s['key']: s['health']['state'] for s in sources.status_all(include_network=False)}
    assert kinds['public_reference'] == sources.REFERENCE_ONLY
    assert kinds['satnogs'] == sources.METADATA_ONLY


def test_online_requires_a_recent_observation_and_not_merely_a_reachable_service():
    fresh = Feed(last=_ago(60)).status(probe=True)
    assert fresh['health']['state'] == sources.ONLINE
    assert fresh['health']['age_s'] < 3600

    old = Feed(last=_ago(7200)).status(probe=True)
    assert old['health']['reachable'] == sources.ONLINE, 'the service itself answered'
    assert old['health']['state'] == sources.STALE, 'but nothing recent has come from it'
    assert old['health']['age_s'] > old['health']['freshness_s']


def test_a_feed_that_has_never_delivered_anything_here_is_not_online():
    never = Feed(last=None).status(probe=True)
    assert never['health']['state'] == sources.STALE
    assert never['health']['last_data_utc'] is None


def test_reachability_still_wins_when_the_source_is_down():
    for reachable in (sources.OFFLINE, sources.DEGRADED, sources.NOT_CONFIGURED,
                      sources.AUTH_REQUIRED, sources.UNSUPPORTED):
        assert Feed(reachable=reachable, last=_ago(1)).status()['health']['state'] == reachable


def test_a_check_that_raises_reports_offline_rather_than_crashing_the_registry():
    class Broken(Feed):
        def check(self, timeout=8):
            raise TimeoutError('the directory did not answer')

    health = Broken(last=_ago(1)).status()['health']
    assert health['state'] == sources.OFFLINE and 'TimeoutError' in health['detail']


def test_the_offline_answer_says_it_was_not_checked_rather_than_guessing():
    health = Feed(last=_ago(1)).status(probe=False)['health']
    assert health['reachable'] == sources.NOT_CONFIGURED
    assert 'not checked' in health['detail']
    assert health['last_data_utc'] is not None, 'what this machine received is a local fact'


def test_freshness_is_published_so_the_rule_can_be_checked_not_taken_on_trust():
    by_key = {s['key']: s for s in sources.status_all(include_network=False)}
    assert by_key['public_sdr']['health']['freshness_s'] == 24 * 3600
    # A local capability is not an observation stream; saying so explicitly is the honest form.
    assert by_key['user_capture']['health']['freshness_s'] is None


@pytest.mark.parametrize('state', [sources.AUTH_REQUIRED, sources.UNSUPPORTED])
def test_states_no_source_produces_today_are_recorded_as_such(state):
    """Part of the vocabulary, deliberately unused. This test is the record that nothing in the
    registry has ever returned either, so neither may be presented as exercised."""
    produced = {s['health']['reachable'] for s in sources.status_all(include_network=False)}
    assert state not in produced
