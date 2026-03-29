from ..base.renderer import BaseRenderer


class ZeroTierRenderer(BaseRenderer):
    """
    ZeroTier Renderer
    """

    def cleanup(self, output):
        # remove last newline
        if output.endswith("\n\n"):
            output = output[0:-1]
        return output
