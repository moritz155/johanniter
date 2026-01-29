from app import app, db, ShiftConfig, Squad
import unittest

class SessionTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_session_isolation(self):
        # User A
        client_a = app.test_client()
        # Initialize
        with client_a:
            res = client_a.get('/api/init')
            self.assertEqual(res.status_code, 200)
            
            # Start Config
            client_a.post('/api/config', json={'location': 'Location A'})
            
            # Create Squad
            client_a.post('/api/squads', json={'name': 'Squad A'})
            
            # Verify A sees it
            res = client_a.get('/api/init')
            data = res.get_json()
            self.assertEqual(data['config']['location'], 'Location A')
            self.assertEqual(len(data['squads']), 1)
            self.assertEqual(data['squads'][0]['name'], 'Squad A')

        # User B
        client_b = app.test_client()
        with client_b:
            res = client_b.get('/api/init')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            
            # Verify B sees nothing (config might be None, squads empty)
            self.assertIsNone(data['config'])
            self.assertEqual(len(data['squads']), 0)
            
            # Start Config B
            client_b.post('/api/config', json={'location': 'Location B'})
            client_b.post('/api/squads', json={'name': 'Squad B'})
            
            # Verify B sees only B
            res = client_b.get('/api/init')
            data = res.get_json()
            self.assertEqual(data['config']['location'], 'Location B')
            self.assertEqual(len(data['squads']), 1)
            self.assertEqual(data['squads'][0]['name'], 'Squad B')

if __name__ == '__main__':
    unittest.main()
