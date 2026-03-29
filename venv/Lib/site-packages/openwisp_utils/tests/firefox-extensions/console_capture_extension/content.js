(function () {
  const script = document.createElement("script");
  script.textContent = `
        (function() {
            if (window._console_logs) return;  // Prevent multiple injections

            window._console_logs = [];

            function mapLogLevel(method) {
                const levelMapping = {
                    log: "INFO",
                    info: "INFO",
                    debug: "DEBUG",
                    warn: "WARNING",
                    error: "SEVERE",
                    trace: "DEBUG",
                    assert: "SEVERE"
                };
                return levelMapping[method] || "INFO"; // Default to INFO
            }

            function captureConsole(method) {
                const original = console[method];
                console[method] = function(...args) {
                    const logLevel = mapLogLevel(method);
                    window._console_logs.push({
                        level: logLevel,
                        message: args.map(arg => (typeof arg === "object" ? JSON.stringify(arg) : String(arg))).join(" ")
                    });
                    original.apply(console, args);
                };
            }

            const methods = ["log", "info", "debug", "warn", "error", "trace", "assert"];
            methods.forEach(captureConsole);
        })();
    `;

  // Ensure script runs in page context
  const head = document.head || document.documentElement;
  head.appendChild(script);
})();
