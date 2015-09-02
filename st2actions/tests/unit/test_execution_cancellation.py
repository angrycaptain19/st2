# Licensed to the StackStorm, Inc ('StackStorm') under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy

import mock

# XXX: actionsensor import depends on config being setup.
import st2tests.config as tests_config
tests_config.parse_args()

import st2actions.bootstrap.runnersregistrar as runners_registrar
from st2actions.runners import ActionRunner
from st2actions.runners.localrunner import LocalShellRunner
from st2common.constants import action as action_constants
from st2common.models.db.liveaction import LiveActionDB
from st2common.models.api.action import ActionAPI
from st2common.persistence.action import Action
from st2common.persistence.liveaction import LiveAction
from st2common.services import action as action_service
from st2common.transport.liveaction import LiveActionPublisher
from st2common.transport.publishers import CUDPublisher
from st2tests.fixtures import executions as fixture
from st2tests import DbTestCase
from tests.unit.base import MockLiveActionPublisher


@mock.patch.object(LocalShellRunner, 'run',
                   mock.MagicMock(return_value=(action_constants.LIVEACTION_STATUS_RUNNING,
                                                'Non-empty', None)))
@mock.patch.object(CUDPublisher, 'publish_create',
                   mock.MagicMock(side_effect=MockLiveActionPublisher.publish_create))
@mock.patch.object(LiveActionPublisher, 'publish_state',
                   mock.MagicMock(side_effect=MockLiveActionPublisher.publish_state))
class ExecutionCancellationTest(DbTestCase):

    @classmethod
    def setUpClass(cls):
        super(ExecutionCancellationTest, cls).setUpClass()
        runners_registrar.register_runner_types()
        action_local = ActionAPI(**copy.deepcopy(fixture.ARTIFACTS['actions']['local']))
        Action.add_or_update(ActionAPI.to_model(action_local))

    def tearDown(self):
        super(ExecutionCancellationTest, self).tearDown()

    def test_basic_cancel(self):
        liveaction = LiveActionDB(action='executions.local', parameters={'cmd': 'uname -a'})
        liveaction, _ = action_service.request(liveaction)
        liveaction = LiveAction.get_by_id(str(liveaction.id))
        self.assertEqual(liveaction.status, action_constants.LIVEACTION_STATUS_RUNNING)

        # Cancel execution.
        action_service.request_cancellation(liveaction)
        liveaction = LiveAction.get_by_id(str(liveaction.id))
        self.assertEqual(liveaction.status, action_constants.LIVEACTION_STATUS_CANCELED)
        self.assertDictEqual(liveaction.result, {'message': 'Action canceled by user.'})

    @mock.patch.object(ActionRunner, 'cancel',
                       mock.MagicMock(side_effect=Exception('Mock cancellation failure.')))
    def test_failed_cancel(self):
        liveaction = LiveActionDB(action='executions.local', parameters={'cmd': 'uname -a'})
        liveaction, _ = action_service.request(liveaction)
        liveaction = LiveAction.get_by_id(str(liveaction.id))
        self.assertEqual(liveaction.status, action_constants.LIVEACTION_STATUS_RUNNING)

        # Cancel execution.
        action_service.request_cancellation(liveaction)

        # Cancellation failed and execution state remains "canceling".
        ActionRunner.cancel.assert_called_once_with()
        liveaction = LiveAction.get_by_id(str(liveaction.id))
        self.assertEqual(liveaction.status, action_constants.LIVEACTION_STATUS_CANCELING)
