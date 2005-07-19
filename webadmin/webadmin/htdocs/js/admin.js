function toggleClass(element, class1, class2) {
    function indexOf(array, obj) {
        if (obj) {
            for (var i = 0; i < array.length; i++) {
                if (array[i] == obj) return i;
            }
        }
        return array.length;
    }
    var classNames = element.className.split(/\s+/) || [];
    var classIndex = indexOf(classNames, class1);
    if (classIndex >= classNames.length) {
        classIndex = indexOf(classNames, class2);
        var tmp = class1;
        class1 = class2;
        class2 = tmp;
    }
    classNames.splice(classIndex, class1 ? 1 : 0, class2);
    element.className = classNames.join(' ');
}

var fragmentId = document.location.hash;
if (fragmentId) {
    fragmentId = fragmentId.substr(1);
}

function enableFolding(triggerId) {
    var trigger = document.getElementById(triggerId);
    if (!trigger) return;
    toggleClass(trigger.parentNode,
                triggerId != fragmentId ? "collapsed" : "expanded");

    var link = document.createElement("a");
    link.href = "#" + triggerId;
    trigger.parentNode.replaceChild(link, trigger);
    link.appendChild(trigger);

    trigger.style.cursor = "pointer";
    addEvent(link, "click", function() {
        toggleClass(link.parentNode, "expanded", "collapsed");
    });
}
