import unittest
import json
from unittest.mock import patch, MagicMock
from bson import ObjectId

# It's important to create the Flask app and register the blueprint
# before importing the app in the test file.
# We will assume the app is created in `app.py` and the blueprint is `api_bp` from `modules.api`.
# We will need to adjust the imports based on the actual project structure.
from app import create_app

class TestApi(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config['TESTING'] = True
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @patch('flask.current_app.mongo_db')
    def test_get_settings_empty(self, mock_db):
        # Mock the database to return no settings
        mock_db.settings.find_one.return_value = None
        
        response = self.app.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {})

    @patch('flask.current_app.mongo_db')
    def test_get_settings_with_data(self, mock_db):
        # Mock the database to return some settings
        settings_data = {'_id': 'global_settings', 'jiraUrl': 'https://jira.example.com'}
        mock_db.settings.find_one.return_value = settings_data
        
        response = self.app.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        # Mongo returns _id as an object, but the API returns it as a string
        settings_data['_id'] = 'global_settings'
        self.assertEqual(response.json, settings_data)

    @patch('flask.current_app.mongo_db')
    def test_post_settings(self, mock_db):
        # Mock the database update operation
        mock_db.settings.update_one.return_value = MagicMock()
        
        settings_data = {'jiraUrl': 'https://jira.example.com'}
        response = self.app.post('/api/settings', 
                                  data=json.dumps(settings_data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"message": "Settings saved successfully."})
        mock_db.settings.update_one.assert_called_once_with(
            {'_id': 'global_settings'},
            {'$set': settings_data},
            upsert=True
        )


    @patch('flask.current_app.mongo_db')
    def test_get_release_detail_found(self, mock_db):
        release_id = ObjectId()
        release_data = {'_id': release_id, 'name': 'Release 1'}
        mock_db.releases.find_one.return_value = release_data

        response = self.app.get(f'/api/releases/{str(release_id)}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], 'Release 1')
        self.assertEqual(response.json['_id'], str(release_id))

    @patch('flask.current_app.mongo_db')
    def test_get_release_detail_not_found(self, mock_db):
        release_id = ObjectId()
        mock_db.releases.find_one.return_value = None

        response = self.app.get(f'/api/releases/{str(release_id)}')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'error': 'Release not found'})

    @patch('flask.current_app.mongo_db')
    def test_put_release_detail(self, mock_db):
        release_id = ObjectId()
        update_data = {'name': 'Updated Release'}

        response = self.app.put(f'/api/releases/{str(release_id)}',
                                data=json.dumps(update_data),
                                content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'message': 'Release updated successfully.'})
        mock_db.releases.update_one.assert_called_once_with(
            {'_id': release_id},
            {'$set': update_data}
        )

    @patch('flask.current_app.mongo_db')
    def test_delete_release_detail(self, mock_db):
        release_id = ObjectId()

        response = self.app.delete(f'/api/releases/{str(release_id)}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'message': 'Release deleted successfully.'})
        mock_db.releases.delete_one.assert_called_once_with({'_id': release_id})


    @patch('modules.api.generate_final_markdown')
    @patch('modules.api.get_summary_from_ai')
    @patch('modules.api.fetch_jira_ticket')
    @patch('modules.api.fetch_jira_tickets_by_jql')
    @patch('subprocess.run')
    @patch('modules.api.generate_supported_platforms_md')
    @patch('modules.api.generate_supported_software_md')
    @patch('modules.api.process_upstream_bugs')
    @patch('modules.api.resolve_introduction')
    @patch('flask.current_app.mongo_db')
    def test_generate_release_notes_success(self, mock_db, mock_resolve_intro, mock_process_upstream, mock_gen_sw, mock_gen_plat, mock_subprocess, mock_fetch_jql, mock_fetch_ticket, mock_get_summary, mock_gen_final_md):
        release_id = ObjectId()
        settings_data = {'_id': 'global_settings', 'jiraUrl': 'a', 'jiraEmail': 'b', 'jiraToken': 'c', 'geminiToken': 'd'}
        release_data = {'_id': release_id, 'name': 'Release 1', 'jiraReleaseId': '123'}

        mock_db.settings.find_one.return_value = settings_data
        mock_db.releases.find_one.return_value = release_data
        mock_resolve_intro.return_value = "Introduction"
        mock_process_upstream.return_value = "Upstream Bugs"
        mock_gen_sw.return_value = "Supported Software"
        mock_gen_plat.return_value = "Supported Platforms"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="Certified Images")
        mock_fetch_jql.return_value = [{'key': 'PROJ-1'}]
        mock_fetch_ticket.return_value = {'key': 'PROJ-1', 'fields': {'summary': 'Test Ticket'}}
        mock_get_summary.return_value = "AI Summary"
        mock_gen_final_md.return_value = "Final Markdown"

        response = self.app.post(f'/api/releases/{str(release_id)}/generate')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'markdown': 'Final Markdown'})


    @patch('flask.current_app.mongo_db')
    def test_generate_release_notes_release_not_found(self, mock_db):
        release_id = ObjectId()
        mock_db.releases.find_one.return_value = None

        response = self.app.post(f'/api/releases/{str(release_id)}/generate')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'error': 'Release not found'})

    @patch('flask.current_app.mongo_db')
    def test_generate_release_notes_incomplete_settings(self, mock_db):
        release_id = ObjectId()
        settings_data = {'_id': 'global_settings', 'jiraUrl': 'a', 'jiraEmail': 'b'}
        release_data = {'_id': release_id, 'name': 'Release 1'}

        mock_db.settings.find_one.return_value = settings_data
        mock_db.releases.find_one.return_value = release_data

        response = self.app.post(f'/api/releases/{str(release_id)}/generate')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {'error': 'JIRA settings are incomplete. Please configure them on the Settings page.'})

    @patch('modules.api.generate_final_markdown')
    @patch('modules.api.get_summary_from_ai')
    @patch('modules.api.fetch_jira_ticket')
    @patch('modules.api.fetch_jira_tickets_by_jql')
    @patch('subprocess.run')
    @patch('modules.api.generate_supported_platforms_md')
    @patch('modules.api.generate_supported_software_md')
    @patch('modules.api.process_upstream_bugs')
    @patch('modules.api.resolve_introduction')
    @patch('flask.current_app.mongo_db')
    def test_generate_release_notes_no_jira_tickets(self, mock_db, mock_resolve_intro, mock_process_upstream, mock_gen_sw, mock_gen_plat, mock_subprocess, mock_fetch_jql, mock_fetch_ticket, mock_get_summary, mock_gen_final_md):
        release_id = ObjectId()
        settings_data = {'_id': 'global_settings', 'jiraUrl': 'a', 'jiraEmail': 'b', 'jiraToken': 'c', 'geminiToken': 'd'}
        release_data = {'_id': release_id, 'name': 'Release 1', 'additionalJiraTickets': 'PROJ-1'}

        mock_db.settings.find_one.return_value = settings_data
        mock_db.releases.find_one.return_value = release_data
        mock_fetch_jql.return_value = []
        mock_fetch_ticket.return_value = None

        response = self.app.post(f'/api/releases/{str(release_id)}/generate')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {'error': 'Could not fetch data for any JIRA tickets.'})

if __name__ == '__main__':
    unittest.main()