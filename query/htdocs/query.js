function initializeFilters() {

  // Removes an existing row from the filters table
  function removeFilter(button, propertyName) {
    var tr = getAncestorByTagName(button, "tr");
    var table = getAncestorByTagName(tr, "table");

    // Ugly hack: Safari removes the DOM nodes, but not the form elements for
    // some buggy reason, so they'll get submitted twice. Setting the name of
    // the original elements to an empty string before removing them seems to
    // solve the problem
    var inputs = tr.getElementsByTagName("input");
    for (var j = 0; j < inputs.length; j++) inputs[j].name = "";
    var selects = tr.getElementsByTagName("select");
    for (var j = 0; j < selects.length; j++) selects[j].name = "";

    table.deleteRow(tr.rowIndex);

    var select = document.forms["query"].elements["add_filter"];
    for (var i = 0; i < select.options.length; i++) {
      var option = select.options[i];
      if (option.value == propertyName) option.disabled = false;
    }
  }

  // Initializes a filter row, the 'input' parameter is the submit
  // button for removing the filter
  function initializeFilter(input) {
    var button = document.createElement("input");
    button.type = "button";
    button.value = input.value;
    button.onclick = function() {
      removeFilter(button, input.name.substr(10));
      return false;
    }
    input.parentNode.replaceChild(button, input);
  }

  // Make the submit buttons for removing filters client-side triggers
  var filters = document.getElementById("filters");
  var inputs = filters.getElementsByTagName("input");
  for (var i = 0; i < inputs.length; i++) {
    var input = inputs[i];
    if (input.type == "submit" && input.name
     && input.name.match(/^rm_filter_/)) {
      initializeFilter(input);
    }
  }

  // Make the drop-down menu for adding a filter a client-side trigger
  var select = document.getElementById("add_filter");
  select.onchange = function() {
    if (select.selectedIndex < 1) return;

    if (select.options[select.selectedIndex].disabled) {
      // Neither IE nor Safari supported disabled options at the time this was
      // written, so alert the user
      alert("A filter already exists for that property");
      return;
    }

    // Convenience function for creating a <label>
    function createLabel(text, htmlFor) {
      var label = document.createElement("label");
      if (text) label.appendChild(document.createTextNode(text));
      if (htmlFor) label.htmlFor = htmlFor;
      return label;
    }

    // Convenience function for creating an <input type="checkbox">
    function createCheckbox(name, value, id) {
      var input = document.createElement("input");
      input.type = "checkbox";
      if (name) input.name = name;
      if (value) input.value = value;
      if (id) input.id = id;
      return input;
    }

    // Convenience function for creating a <select>
    function createSelect(name, options, id) {
      var select = document.createElement("select");
      if (name) select.name = name;
      if (options) {
        for (var i = 0; i < options.length; i++) {
          var option;
          if (typeof(options[i]) == "object") {
            option = new Option(options[i].text, options[i].value);
          } else {
            option = new Option(options[i], options[i]);
          }
          select.options[select.options.length] = option;
        }
      }
      if (id) select.id = id;
      return select;
    }

    var propertyName = select.options[select.selectedIndex].value;
    var property = properties[propertyName];
    var table = document.getElementById("filters").getElementsByTagName("table")[0];
    var tr = document.createElement("tr");
    tr.className = propertyName;

    // Add the row header
    var th = document.createElement("th");
    th.scope = "row";
    th.appendChild(createLabel(property.label));
    tr.appendChild(th);

    var td = document.createElement("td");
    if (property.type == "radio") {
      td.colSpan = 2;
      td.className = "filter";
      for (var i = 0; i < property.options.length; i++) {
        var option = property.options[i];
        // Another hack for Safari/WebCore, which will not submit dynamically
        // created checkboxes with the vale set for them, but rather with the
        // default value 'on'
        td.appendChild(createCheckbox("__" + propertyName + ":" + option, option,
          propertyName + "_" + option));
        td.appendChild(createLabel(option, propertyName + "_" + option));
      }
      tr.appendChild(td);
    } else {
      // Add the mode selector
      td.className = "mode";
      var modeSelect = createSelect(propertyName + "_mode", modes[property.type]);
      td.appendChild(modeSelect);
      tr.appendChild(td);

      // Add the selector or text input for the actual filter value
      td = document.createElement("td");
      td.className = "filter";
      if (property.type == "select") {
        var element = createSelect(propertyName, property.options);
      } else if (property.type == "text") {
        var element = document.createElement("input");
        element.name = propertyName;
        element.size = 42;
      }
      td.appendChild(element);
      element.focus();
      tr.appendChild(td);
    }

    // Add the remove buttons
    td = document.createElement("td");
    td.className = "actions";
    var removeButton = document.createElement("input");
    removeButton.type = "button";
    removeButton.name = "rm_filter_" + propertyName;
    removeButton.value = "-";
    removeButton.onclick = function() { removeFilter(removeButton, propertyName) };
    td.appendChild(removeButton);
    tr.appendChild(td);

    // Find the insertion point for the new row. We try to keep the filter rows
    // in the same order as the options in the 'Add filter' drop-down, because
    // that's the order they'll appear in when submitted.
    var insertionPoint = getAncestorByTagName(select, "tr");
    outer: for (var i = select.selectedIndex + 1; i < select.options.length; i++) {
      for (var j = 0; j < table.rows.length; j++) {
        if (table.rows[j].className == select.options[i].value) {
          insertionPoint = table.rows[j];
          break outer;
        }
      }
    }

    // Finally add the new row to the table
    if (table.tBodies && table.tBodies.length) {
      table.tBodies[0].insertBefore(tr, insertionPoint);
    } else { // real XHTML
      table.insertBefore(tr, insertionPoint);
    }

    // Disable the add filter in the drop-down list
    select.options[select.selectedIndex].disabled = true;
    select.selectedIndex = -1;
  }
}
