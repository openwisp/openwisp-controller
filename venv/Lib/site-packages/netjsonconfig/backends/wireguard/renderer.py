from ..base.renderer import BaseRenderer


class WireguardRenderer(BaseRenderer):
    """
    Wireguard Renderer
    """

    def cleanup(self, output):
        # remove indentations
        output = output.replace("    ", "")
        # remove last newline
        if output.endswith("\n\n"):
            output = output[0:-1]
        return output
