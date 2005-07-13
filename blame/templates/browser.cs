<?cs include "header.cs"?>
<?cs include "macros.cs"?>

<div id="ctxtnav" class="nav">
 <ul>
  <li class="last"><a href="<?cs var:browser.log_href ?>">Revision Log</a></li>
 </ul>
</div>

<div id="content" class="browser">
 <h1><?cs call:browser_path_links(browser.path, browser) ?></h1>

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
   </tbody><?cs
   if:len(browser.props) ?><tbody><tr><td class="props" colspan="5"><ul><?cs
    each:prop = browser.props ?><li>Property <strong><?cs
      var:name(prop) ?></strong> set to <em><code><?cs
      var:prop ?></code></em></li><?cs
    /each ?></ul></td></tr></tbody><?cs
   /if ?>
  </table><?cs

 else ?>
  <form method="get" id="prefs" action=""><div>
    <label>View revision:
    <input type="text" id="rev" name="rev" value="<?cs
      var:browser.revision ?>" size="5" /></label>
    <fieldset id="annotations"><legend>Show annotations:</legend><?cs
     each:annotation = file.annotations ?>
      <label><input name="<?cs var:annotation.name ?>" type="checkbox"<?cs
        if:annotation.enabled ?> checked="checked"<?cs /if ?> <?cs
        if:annotation.name == 'lineno' ?> disabled="disabled"<?cs /if ?>> <?cs 
        var:annotation.label ?></label> <?cs
     /each ?></fieldset>
    <div class="buttons"><input type="submit" value="Update" /></div>
  </div></form>
  <dl id="overview">
   <dt class="time">Last Modified:</dt>
   <dd class="time"><?cs var:file.modified.age ?> ago (<?cs
     var:file.modified.date ?>) by <?cs
     var:file.modified.author ?> in <a href="<?cs
     var:file.modified.changeset_href ?>" title="<?cs 
     var:file.modified.message ?>">[<?cs var:file.modified.rev ?>]</a></dd>
   <dt class="time">Created:</dt>
   <dd class="time"><?cs var:file.created.age ?> ago (<?cs
     var:file.created.date ?>) by <?cs
     var:file.created.author ?> in <a href="<?cs
     var:file.created.changeset_href ?>" title="<?cs 
     var:file.created.message ?>">[<?cs var:file.created.rev ?>]</a></dd><?cs
   if:len(browser.props) ?>
    <dt class="props">Properties:</dt>
    <dd class="props"><ul><?cs
    each:prop = browser.props ?><li><code><em><?cs
      var:name(prop) ?></code></em> set to <q><code><?cs
      var:prop ?></code></q></li><?cs
    /each ?></ul></dd><?cs
   /if ?>
  </dl>
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

</div>
<?cs include:"footer.cs"?>
