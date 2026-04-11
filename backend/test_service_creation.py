import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.meta_api import create_meta_template

class TestMetaService(unittest.TestCase):
    
    @patch('app.services.meta_api.requests.post')
    def test_body_example_flattening(self, mock_post):
        # Setup mock response
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"id": "12345", "status": "PENDING"}
        mock_post.return_value = mock_res
        
        # Input with NESTED list (common frontend error)
        components = [
            {
                "type": "BODY",
                "text": "Hello {{1}}, your bonus is {{2}}.",
                "example": {
                    "body_text": [ ["John", "$50"] ]
                }
            }
        ]
        
        create_meta_template("test_tpl", "MARKETING", "en_US", components)
        
        # Verify the payload sent to requests.post
        args, kwargs = mock_post.call_args
        sent_payload = kwargs['json']
        
        body_comp = next(c for c in sent_payload['components'] if c['type'] == 'BODY')
        
        # ASSERTION: body_text should be a FLAT list [ "John", "$50" ], not [ [ "John", "$50" ] ]
        self.assertEqual(body_comp['example']['body_text'], ["John", "$50"])
        print("Success: Nested body_text example was correctly flattened.")

    @patch('app.services.meta_api.requests.post')
    def test_media_header_handle(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"id": "12345"}
        mock_post.return_value = mock_res
        
        components = [
            {
                "type": "HEADER",
                "format": "IMAGE",
                "example": {
                    "header_handle": "h/123456789" # Common mistake: sending string instead of list
                }
            },
            {
                "type": "BODY",
                "text": "Check this image!"
            }
        ]
        
        create_meta_template("test_media_tpl", "MARKETING", "en_US", components)
        
        args, kwargs = mock_post.call_args
        sent_payload = kwargs['json']
        
        header_comp = next(c for c in sent_payload['components'] if c['type'] == 'HEADER')
        
        # ASSERTION: header_handle should be a list
        self.assertIsInstance(header_comp['example']['header_handle'], list)
        self.assertEqual(header_comp['example']['header_handle'][0], "h/123456789")
        print("Success: Media header handle was correctly wrapped in a list.")

if __name__ == "__main__":
    unittest.main()
