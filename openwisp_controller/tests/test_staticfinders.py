import unittest

from openwisp_controller.staticfiles import DependencyFinder


class TestStaticFinders(unittest.TestCase):
    def test_dependency_finder(self):
        finder = DependencyFinder()
        self.assertIsInstance(finder.locations, list)
