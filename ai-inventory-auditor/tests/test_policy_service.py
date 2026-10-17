import unittest
from business.policy_service import PolicyService

class TestPolicyService(unittest.TestCase):
    def setUp(self):
        self.service = PolicyService()

    def test_classifies_variance_from_current_policy(self):
        self.assertEqual(self.service.classify_variance(-17), "HIGH")
        self.assertEqual(self.service.classify_variance(-5), "NORMAL")
        self.assertEqual(self.service.classify_variance(0), "NONE")
        self.assertEqual(self.service.classify_variance(None), "UNKNOWN")

if __name__ == "__main__":
    unittest.main()
