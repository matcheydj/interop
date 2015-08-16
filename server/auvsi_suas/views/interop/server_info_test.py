"""Tests for the server_info module."""

import time
import json
import logging
from auvsi_suas.models import AerialPosition
from auvsi_suas.models import GpsPosition
from auvsi_suas.models import MissionConfig
from auvsi_suas.models import ServerInfo
from auvsi_suas.models import ServerInfoAccessLog
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import TestCase


class TestGetServerInfoView(TestCase):
    """Tests the server_info view."""

    def setUp(self):
        """Sets up the client, server info URL, and user."""
        cache.clear()
        self.user = User.objects.create_user('testuser', 'testemail@x.com',
                                             'testpass')
        self.user.save()

        self.info = ServerInfo()
        self.info.team_msg = 'test message'
        self.info.save()

        gpos = GpsPosition(latitude=0, longitude=0)
        gpos.save()

        self.mission = MissionConfig()
        self.mission.is_active = True
        self.mission.home_pos = gpos
        self.mission.mission_waypoints_dist_max = 0
        self.mission.emergent_last_known_pos = gpos
        self.mission.off_axis_target_pos = gpos
        self.mission.sric_pos = gpos
        self.mission.ir_primary_target_pos = gpos
        self.mission.ir_secondary_target_pos = gpos
        self.mission.air_drop_pos = gpos
        self.mission.server_info = self.info
        self.mission.save()

        self.login_url = reverse('auvsi_suas:login')
        self.info_url = reverse('auvsi_suas:server_info')
        logging.disable(logging.CRITICAL)

    def test_not_authenticated(self):
        """Tests requests that have not yet been authenticated."""
        client = self.client
        info_url = self.info_url

        response = client.get(info_url)
        self.assertEqual(403, response.status_code)

    def test_invalid_request(self):
        """Tests an invalid request by mis-specifying parameters."""
        client = self.client
        login_url = self.login_url
        info_url = self.info_url

        client.post(login_url,
                    {'username': 'testuser',
                     'password': 'testpass'})
        response = client.post(info_url)
        self.assertEqual(response.status_code, 400)

    def test_no_active_mission(self):
        """Tests that no active mission returns 500."""
        self.mission.is_active = False
        self.mission.save()

        client = self.client
        login_url = self.login_url
        info_url = self.info_url
        client.post(login_url,
                    {'username': 'testuser',
                     'password': 'testpass'})

        response = client.get(info_url)
        self.assertEqual(response.status_code, 500)

    def test_correct_log_and_response(self):
        """Tests that access is logged and returns valid response."""
        client = self.client
        login_url = self.login_url
        info_url = self.info_url
        client.post(login_url,
                    {'username': 'testuser',
                     'password': 'testpass'})

        response = client.get(info_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(ServerInfoAccessLog.objects.all()), 1)
        access_log = ServerInfoAccessLog.objects.all()[0]
        self.assertEqual(access_log.user, self.user)
        json_data = json.loads(response.content)
        self.assertTrue('server_info' in json_data)
        self.assertTrue('server_time' in json_data)

    def test_loadtest(self):
        """Tests the max load the view can handle."""
        if not settings.TEST_ENABLE_LOADTEST:
            return

        client = self.client
        login_url = self.login_url
        info_url = self.info_url
        client.post(login_url,
                    {'username': 'testuser',
                     'password': 'testpass'})

        total_ops = 0
        start_t = time.clock()
        while time.clock() - start_t < settings.TEST_LOADTEST_TIME:
            client.get(info_url)
            total_ops += 1
        end_t = time.clock()
        total_t = end_t - start_t
        op_rate = total_ops / total_t

        print 'Server Info Rate (%f)' % op_rate
        self.assertGreaterEqual(
            op_rate, settings.TEST_LOADTEST_INTEROP_MIN_RATE)
