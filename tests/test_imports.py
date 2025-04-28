"""
Test module to verify that all modules can be imported correctly.
This test ensures there are no import errors, circular dependencies, or missing modules.
"""
import unittest
import importlib
import sys


class TestImports(unittest.TestCase):
    """Test class to verify all modules can be imported without errors."""
    
    def test_all_module_imports(self):
        """Test that all modules can be imported without errors."""
        modules = [
            "portfolio_generator.modules.logging",
            "portfolio_generator.modules.utils",
            "portfolio_generator.modules.search_utils",
            "portfolio_generator.modules.section_generator",
            "portfolio_generator.modules.data_extraction",
            "portfolio_generator.modules.portfolio_generator",
            "portfolio_generator.modules.report_upload",
            "portfolio_generator.modules.report_generator",
            "portfolio_generator.modules.main",
            "portfolio_generator.modules.web_search",
            "portfolio_generator.modules.news_update_generator",
            # Also test the compatibility layers
            "portfolio_generator.web_search",
            "portfolio_generator.news_update_generator",
        ]
        
        for module_name in modules:
            try:
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module, f"Failed to import {module_name}")
                print(f"✅ Successfully imported {module_name}")
            except Exception as e:
                self.fail(f"Error importing {module_name}: {str(e)}")
    
    def test_circular_dependencies(self):
        """Test that there are no circular dependencies between modules."""
        # Use a simple approach to detect circular imports by looking at module.__dict__
        modules_to_check = [
            "portfolio_generator.modules.logging",
            "portfolio_generator.modules.utils", 
            "portfolio_generator.modules.section_generator",
            "portfolio_generator.modules.web_search",
            "portfolio_generator.modules.news_update_generator",
        ]
        
        for module_name in modules_to_check:
            try:
                # Force a fresh import by removing from sys.modules if present
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                # Import the module
                module = importlib.import_module(module_name)
                
                # Check this module doesn't import itself through other modules
                for attr_name, attr_value in module.__dict__.items():
                    if attr_name.startswith("_"):  # Skip private attributes
                        continue
                    
                    # If the attribute is a module, check it doesn't create a circular reference
                    if hasattr(attr_value, "__name__") and hasattr(attr_value, "__file__"):
                        self.assertFalse(
                            module_name in str(attr_value.__name__),
                            f"Circular dependency detected: {module_name} -> {attr_value.__name__}"
                        )
                
                print(f"✅ No circular dependencies detected in {module_name}")
            except Exception as e:
                self.fail(f"Error checking {module_name} for circular dependencies: {str(e)}")


if __name__ == "__main__":
    unittest.main()
