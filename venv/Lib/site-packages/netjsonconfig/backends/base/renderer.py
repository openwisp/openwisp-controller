from jinja2 import Environment, PackageLoader


class BaseRenderer(object):
    """
    Base Renderer class
    Renderers are used to generate a string
    which represents the router configuration
    """

    def __init__(self, backend):
        self.config = backend.config
        self.backend = backend

    @property
    def env_path(self):
        return self.__module__

    @property
    def template_env(self):
        return Environment(
            loader=PackageLoader(self.env_path, "templates"), trim_blocks=True
        )

    @classmethod
    def get_name(cls):
        """
        Returns the name of the render class without its prefix
        """
        return str(cls.__name__).replace("Renderer", "").lower()

    def cleanup(self, output):
        """
        Performs cleanup of output (indentation, new lines)

        :param output: string representation of the client configuration
        """
        return output

    def render(self):
        """
        Renders configuration by using the jinja2 templating engine
        """
        # get jinja2 template
        template_name = "{0}.jinja2".format(self.get_name())
        template = self.template_env.get_template(template_name)
        # render template and cleanup
        context = getattr(self.backend, "intermediate_data", {})
        output = template.render(data=context)
        return self.cleanup(output)
