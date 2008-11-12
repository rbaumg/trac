
(function($){

  window.enableBlame = function(url, original_path) {
    var message = null;
    var message_rev = null;
  
    /* for each blame cell... */
    var path = null;
    $("table.code th.blame").each(function() {
      // determine path from the changeset link
      var a = $(this).find("a");
      var href = a.attr("href");
      if ( ! (href || path) )
        return; // was "Rev" column title
      
      if ( href ) {
        a.removeAttr("href");
        var sep = href.slice(href.indexOf("changeset/") + 10).indexOf("/");
        if ( sep > 0 )
          path = elts.slice(sep+1);
        else
          path = original_path;
      }

      // determine rev from th class, which is of the form "blame r123"
      var rev = $(this).attr("class").split(" ")[1];
      if (!rev)
        return;
  
      $(this).css("cursor", "pointer").click(function() {
        var row = this.parentNode;
        var message_is_visible = message && message.css("display") == "block";
        var highlight_rev = null;
  
        function show() {
          /* Display commit message for the selected revision */
  
          var message_w = message.get(0).offsetWidth;
  
          // limit message panel width to 3/5 of the row width
          var row_w = row.offsetWidth;
          var max_w = (3.0 * row_w / 5.0);
          if (!message_w || message_w > max_w) {
            message_w = max_w; 
            var borderw = (3+8)*2; // borderwidth + padding on both sides 
            message.css({width: message_w - borderw + "px"});
          }
  
          var row_offset = $(row).offset();
          var left = row_offset.left + row.offsetWidth - message_w;
          message.css({display: "block", top: row_offset.top+"px", left: left-2+"px"});
        }
  
        function hide() {
          /* Hide commit message */
          message.css({display: "none"});
  
          /* Remove highlighting for lines of the current revision */
          $("table.code th."+message_rev).each(function() { 
            $(this.parentNode).removeClass("hilite") 
          });
        }
  
        if (message_rev != rev) {              // fetch a new revision
          if (message_is_visible) {
            hide();
          }
          message_rev = rev;
          highlight_rev = message_rev;
  
          $.get(url + rev.substr(1), {annotate: path}, function(data) {
            // remove former message panel if any
            if (message)
              message.remove();
            // create new message panel
            message = $('<div class="message">').css("position", "absolute")
                .append($('<div class="inlinebuttons">')
                  .append($('<input value="Close" type="button">').click(hide)))
                .append($('<div>').html(data || "<strong>(no changeset information)</strong>"))
              .appendTo("body");

            // workaround non-clickable "Close" issue in Firefox
            if ($.browser.mozilla || $.browser.safari)
              message.find("div.inlinebuttons").next().css("clear", "right");
  
            show();
          });
        } else if (message_is_visible) {
          hide();
        } else {
          show();
          highlight_rev = message_rev;
        }
  
        /* Highlight all lines of the current revision */
        $("table.code th."+highlight_rev).each(function() { 
          $(this.parentNode).addClass("hilite") 
        });
  
      });
    });
  }

})(jQuery);
