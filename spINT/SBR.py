class SBRBase:
    # Registry to hold all page classes
    registry = {}

    def __init_subclass__(cls, page_name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        
        if page_name is None:
            page_name = cls.__name__.lower()
        cls.page_name = page_name

        SBRBase.registry[page_name] = cls

    def load(self):
        """Each page must implement its own load method."""
        raise NotImplementedError("Subclasses must implement this method.")

# Example page definitions:
class Home(SBRBase, page_name="home"):
    def load(self):
        print("Loading SBR Home Page")
        self.driver.get('https://www3.beratungsring.org/')


# Central navigator that uses the registry:
class SBR:
    def __init__(self, driver):
        self.driver = driver
        self.pages = SBRBase.registry  # All pages are registered here

    @property
    def is_logged_in(self):
        return False

    def login(self, usr, pwd):
        pass

    def go_to_page(self, page_name: str):
        page_class = self.pages.get(page_name)

        if page_class is None:
            raise ValueError(f"Page '{page_name}' not found. Choose one of {list(self.pages.keys())}")

        page_instance = page_class()
        page_instance.load()

# Example usage:
if __name__ == '__main__':
    # 'driver' would be your Selenium WebDriver instance.
    driver = None  # placeholder for the Selenium driver
    navigator = SBR(driver)
    
    # Navigate to different pages using the central registry.
    navigator.go_to_page("home")
    navigator.go_to_page("login")
    navigator.is_logged_in
