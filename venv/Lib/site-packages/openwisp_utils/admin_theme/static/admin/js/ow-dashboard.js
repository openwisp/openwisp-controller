(function () {
  "use strict";

  function slugify(str) {
    str = str.replace(/^\s+|\s+$/g, "");
    // Make the string lowercase
    str = str.toLowerCase();
    // Remove invalid chars
    str = str
      .replace(/[^a-z0-9 -]/g, "")
      // Collapse whitespace and replace by -
      .replace(/\s+/g, "-")
      // Collapse dashes
      .replace(/-+/g, "-");
    return str;
  }

  let elementsParam = Object.values(owDashboardCharts),
    container = document.getElementById("plot-container");

  const layout = {
      height: 410,
      width: 410,
      margin: {
        t: 0,
        b: 0,
      },
      legend: {
        yanchor: "bottom",
        xanchor: "left",
        x: 0,
        y: -0.025,
        bgcolor: "transparent",
        itemclick: false,
      },
      title: {
        yanchor: "auto",
        y: 0.9,
        font: { size: 18 },
      },
    },
    options = {
      displayModeBar: false,
    };

  for (let i = 0; i < elementsParam.length; ++i) {
    layout.title.text = elementsParam[i].name;
    // Remove annotations added from previous chart.
    // Otherwise, empty chart will show annotations from
    // the previous chart.
    delete layout.annotations;
    let data = {
        type: "pie",
        hole: 0.55,
        showlegend: !elementsParam[i].hasOwnProperty("quick_link"),
      },
      element = document.createElement("div"),
      totalValues = 0;

    // Show a graph depicting disabled graph when there is insufficient data
    if (elementsParam[i].query_params.values.length === 0) {
      data.values = [1];
      data.labels = ["Not enough data"];
      data.marker = {
        colors: ["#80808091"],
      };
      data.texttemplate = " ";
      data.showlegend = false;
      data.hovertemplate = "%{label}";
    } else {
      data.values = elementsParam[i].query_params.values;
      data.labels = elementsParam[i].query_params.labels;

      if (data.labels.length > 4) {
        data.showlegend = false;
      }
      data.rotation = 180;
      data.textposition = "inside";
      data.insidetextorientation = "horizontal";

      if (elementsParam[i].colors) {
        data.marker = {
          colors: elementsParam[i].colors,
        };
      }
      data.texttemplate = "%{percent}";
      data.targetLink = elementsParam[i].target_link;
      data.filters = elementsParam[i].filters;
      data.filtering = elementsParam[i].filtering;

      // add total to pie chart
      for (var c = 0; c < data.values.length; c++) {
        totalValues += data.values[c];
      }
    }
    layout.annotations = [
      {
        font: {
          size: 20,
          weight: "bold",
        },
        showarrow: false,
        text: `<b>${totalValues}</b>`,
        x: 0.5,
        y: 0.5,
      },
    ];

    Plotly.newPlot(element, [data], layout, options);

    if (elementsParam[i].query_params.values.length !== 0) {
      element.on("plotly_click", function (data) {
        var path = data.points[0].data.targetLink,
          filters = data.points[0].data.filters,
          filtering = data.points[0].data.filtering,
          i = data.points[0].i;
        if (filtering !== "False") {
          if (filters && typeof filters[i] !== "undefined") {
            path += filters[i];
          } else {
            path += encodeURIComponent(data.points[0].label);
          }
        }
        window.location = path;
      });
    }

    // Add quick link button
    if (elementsParam[i].hasOwnProperty("quick_link")) {
      let quickLinkContainer = document.createElement("div");
      quickLinkContainer.classList.add("quick-link-container");
      let quickLink = document.createElement("a");
      quickLink.href = elementsParam[i].quick_link.url;
      quickLink.innerHTML = elementsParam[i].quick_link.label;
      quickLink.title =
        elementsParam[i].quick_link.title || elementsParam[i].quick_link.label;
      quickLink.classList.add("button", "quick-link");
      // Add custom css classes
      if (elementsParam[i].quick_link.custom_css_classes) {
        for (
          let j = 0;
          j < elementsParam[i].quick_link.custom_css_classes.length;
          ++j
        ) {
          quickLink.classList.add(elementsParam[i].quick_link.custom_css_classes[j]);
        }
      }
      quickLinkContainer.appendChild(quickLink);
      element.appendChild(quickLinkContainer);
    }
    element.classList.add(slugify(elementsParam[i].name));
    container.appendChild(element);
  }
})();
