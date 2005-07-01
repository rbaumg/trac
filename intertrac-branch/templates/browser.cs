<?cs include "header.cs"?>
<?cs include "macros.cs"?>

<div id="ctxtnav" class="nav">
 <ul>
  <li class="first"><a href="<?cs var:browser.diff_href ?>">Last Changes</a></li>
  <li class="last"><a href="<?cs var:browser.log_href ?>">Revision Log</a></li>
 </ul>
</div>


<div id="content" class="browser">
 <h1><?cs 
  if:browser.old_path ?>Current Target for Diff: <?cs
  /if ?><?cs call:browser_path_links(browser.path, browser) ?>
 </h1><?cs
  if:browser.old_path ?><h2>Browse to select a different target</h2><?cs
  /if ?>
 <div id="jumprev">
  <form action="" method="get"><?cs
   if:browser.old_path ?>
    <input type="hidden" name="old_path" value="<?cs var:browser.old_path ?>" />
    <input type="hidden" name="old_rev" value="<?cs var:browser.old_rev ?>" /><?cs
   /if ?>
   <div>
    <label for="rev">View revision:</label>
    <input type="text" id="rev" name="rev" value="<?cs
       var:browser.revision ?>" size="4" />
   </div>
  </form>
 </div>

 <?cs if:browser.is_dir ?>
  <table class="listing" id="dirlist">
   <thead>
    <tr><?cs 
     call:sortable_th(browser.order, browser.desc, 'name', 'Name', browser.href) ?><?cs 
     call:sortable_th(browser.order, browser.desc, 'size', 'Size', browser.href) ?>
     <th class="rev">Rev</th><?cs 
     call:sortable_th(browser.order, browser.desc, 'date', 'Age', browser.href) ?>
     <th class="change">Last Change</th>
    </tr>
   </thead>
   <tbody>
    <?cs if:len(links.up) != "/" ?>
     <tr class="even">
      <td class="name" colspan="4">
       <a class="parent" title="Parent Directory" href="<?cs
         var:links.up.0.href ?>">../</a>
      </td>
     </tr>
    <?cs /if ?>
    <?cs each:item = browser.items ?>
     <?cs set:change = browser.changes[item.rev] ?>
     <tr class="<?cs if:name(item) % #2 ?>even<?cs else ?>odd<?cs /if ?>">
      <td class="name"><?cs
       if:item.is_dir ?><?cs
        if:item.permission ?>
         <a class="dir" title="Browse Directory" href="<?cs
           var:item.browser_href ?>"><?cs var:item.name ?></a><?cs
        else ?>
         <span class="dir" title="Access Denied" href=""><?cs
           var:item.name ?></span><?cs
        /if ?><?cs
       else ?><?cs
        if:item.permission != '' ?>
         <a class="file" title="View File" href="<?cs
           var:item.browser_href ?>"><?cs var:item.name ?></a><?cs
        else ?>
         <span class="file" title="Access Denied" href=""><?cs
           var:item.name ?></span><?cs
        /if ?><?cs
       /if ?>
      </td>
      <td class="size"><?cs var:item.size ?></td>
      <td class="rev"><?cs if:item.permission != '' ?><a title="View Revision Log" href="<?cs
        var:item.log_href ?>"><?cs var:item.rev ?></a><?cs else ?><?cs var:item.rev ?><?cs /if ?></td>
      <td class="age"><span title="<?cs var:browser.changes[item.rev].date ?>"><?cs
        var:browser.changes[item.rev].age ?></span></td>
      <td class="change">
       <span class="author"><?cs var:browser.changes[item.rev].author ?>:</span>
       <span class="change"><?cs var:browser.changes[item.rev].message ?></span>
      </td>
     </tr>
    <?cs /each ?>
   </tbody>
  </table><?cs
 /if ?><?cs

 if:len(browser.props) || !browser.is_dir ?>
  <table id="info" summary="Revision info"><?cs
   if:!browser.is_dir ?><tr>
    <th scope="row">
     Revision <a href="<?cs var:file.changeset_href ?>"><?cs var:file.rev ?></a>
     (checked in by <?cs var:file.author ?>, <?cs var:file.age ?> ago)
    </th>
    <td class="message"><?cs var:file.message ?></td>
   </tr><?cs /if ?><?cs
   if:len(browser.props) ?><tr>
    <td colspan="2"><ul class="props"><?cs
     each:prop = browser.props ?>
      <li>Property <strong><?cs var:name(prop) ?></strong> set to <em><code><?cs
      var:prop ?></code></em></li><?cs
     /each ?>
    </ul></td><?cs
   /if ?></tr>
  </table><?cs
 /if ?><?cs
 
 if:!browser.is_dir ?>
  <div id="preview"><?cs
   if:file.preview ?><?cs
    var:file.preview ?><?cs
   elif:file.max_file_size_reached ?>
    <strong>HTML preview not available</strong>, since file-size exceeds <?cs
    var:file.max_file_size  ?> bytes. Try <a href="<?cs
    var:file.raw_href ?>">downloading</a> the file instead.<?cs
   else ?><strong>HTML preview not available</strong>. To view, <a href="<?cs
    var:file.raw_href ?>">download</a> the file.<?cs
   /if ?>
  </div><?cs
 /if ?>

 <div id="help">
  <strong>Note:</strong> See <a href="<?cs var:trac.href.wiki
  ?>/TracBrowser">TracBrowser</a> for help on using the browser.
 </div>

  <div id="anydiff"><?cs
   if:browser.old_path ?><?cs
    if:browser.old_path == browser.path && browser.old_rev == browser.revision ?>
     <h2>This Path/Revision is the Base for the current Diff operation.</h2><?cs
    else ?>
     <form action="<?cs var:diff.href ?>" method="get">
      <label for="diff">
       <h2>Current Base for Diff: <?cs var:browser.old_path ?> in Revision <?cs var:browser.old_rev ?></h2>
      </label>
      <input type="hidden" name="old_path" value="<?cs var:browser.old_path ?>" />
      <input type="hidden" name="old" value="<?cs var:browser.old_rev ?>" />
      <input type="hidden" name="new" value="<?cs var:browser.revision ?>" />
      <div class="buttons">
        <input type="<?cs if:len(browser.path) > #1 ?>submit<?cs else ?>hidden<?cs /if ?>"
               name="diff" value="Diff" 
               title="Diff the current Path/Revision against the selected Base" />
      </div>
     </form><?cs
    /if ?>
    <form action="<?cs var:browser.href ?>" method="get">
     <input type="hidden" name="diff" value="cancel" />
     <div class="buttons">
      <input type="submit" value="Cancel" 
       title="Cancel the current Diff operation" />
     </div>
    </form><?cs
   elif len(browser.path) > #1 ?>
    <form action="<?cs var:browser.href ?>" method="get">
     <input type="hidden" name="rev" value="<?cs var:browser.revision ?>" />
     <input type="hidden" name="diff" value="replace" />
     <div class="buttons">
      <input type="submit" 
             value="<?cs if:browser.old_path ?>Replace Base for Diff <?cs
                    else ?>Set Base for Diff<?cs /if ?>"
             title="Select the current Path/Revision to be the Base for a Diff operation" />
     </div>
    </form><?cs
   /if ?>
  </div>

</div>
<?cs include:"footer.cs"?>
