<?cs set:html.stylesheet = 'css/browser.css' ?>
<?cs include "header.cs"?>
<?cs include "macros.cs"?>

<div id="ctxtnav" class="nav">
 <ul>
  <li class="last"><a href="<?cs
    var:log.browser_href ?>">View Latest Revision</a></li>
  <li class="last"><?cs
   if:log.action == "path" ?>
    <a title="Revision Log" 
       href="<?cs var:log.log_href ?>">Node History</a><?cs
   else ?>
    <a title="Search for all revisions of the path '<?cs var:log.path ?>...'"
       href="<?cs var:log.path_log_href ?>">Path History</a><?cs
   /if ?>
  </li><?cs
  if:len(links.prev) ?>
   <li class="first<?cs if:!len(links.next) ?> last<?cs /if ?>">
    &larr; <a href="<?cs var:links.prev.0.href ?>" title="<?cs
      var:links.prev.0.title ?>">Newer Revisions</a>
   </li><?cs
  /if ?><?cs
  if:len(links.next) ?>
   <li class="<?cs if:!len(links.prev) ?>first <?cs /if ?>last">
    <a href="<?cs var:links.next.0.href ?>" title="<?cs
      var:links.next.0.title ?>">Older Revisions</a> &rarr;
   </li><?cs
  /if ?>
 </ul>
</div>


<div id="content" class="log">
 <?cs call:browser_path_links(log.path, log) ?>
 <h3><?cs
  if:log.action == "path" ?>
   All Revisions Found on the Current Path, up to Revision <?cs var:log.rev ?><?cs
  else ?>
   Revision Log starting at Revision <?cs var:log.rev ?><?cs
  /if ?><?cs 
  if:len(links.prev) + len(links.next) > #0 ?>
   (Page <?cs var:log.page ?>)<?cs
  /if ?>
 </h3>

 <div class="diff">
  <div id="legend">
   <h3>Legend:</h3>
   <dl>
    <dt class="add"></dt><dd>Added</dd><?cs
    if:log.action == "path" ?>
     <dt class="rem"></dt><dd>Removed</dd><?cs
    /if ?>
    <dt class="mod"></dt><dd>Modified</dd>
    <dt class="cp"></dt><dd>Copied or Renamed</dd>
   </dl>
  </div>
 </div>

 <div id="jumprev">
  <form action="<?cs var:browser_current_href ?>" method="get">
   <div>
    <label for="rev">View revision:</label>
    <input type="text" id="rev" name="rev" value="<?cs
      var:log.items.0.rev ?>" size="4" />
   </div>
  </form>
 </div>

 <table id="chglist" class="listing">
  <thead>
   <tr>
    <th class="change"></th>
    <th class="data">Date</th>
    <th class="rev">Rev</th>
    <th class="chgset">Chgset</th>
    <th class="author">Author</th>
    <th class="summary">Log Message</th>
   </tr>
  </thead>
  <tbody><?cs
   set:indent = #1 ?><?cs
   each:item = log.items ?><?cs
    if:item.old_path && !(log.action == "path" && item.old_path == log.path) ?>
     <tr class="<?cs if:name(item) % #2 ?>even<?cs else ?>odd<?cs /if ?>">
      <td class="old_path" colspan="6" style="padding-left: <?cs var:indent ?>em">
       copied from <a href="<?cs var:item.browser_href ?>"?><?cs var:item.old_path ?></a>:
      </td>
     </tr><?cs
     set:indent = indent + #1 ?><?cs
    elif:log.action == "path" ?><?cs
      set:indent = #1 ?><?cs
    /if ?>
    <tr class="<?cs if:name(item) % #2 ?>even<?cs else ?>odd<?cs /if ?>">
     <td class="change" style="padding-left:<?cs var:indent ?>em">
      <a title="Examine node history starting from here" href="<?cs var:item.log_href ?>">
       <div class="<?cs var:item.change ?>"></div>
       <span class="comment">(<?cs var:item.change ?>)</span>
      </a>
     </td>
     <td class="date"><?cs var:log.changes[item.rev].date ?></td>
     <td class="rev">
      <a href="<?cs var:item.browser_href ?>"><?cs var:item.rev ?></a>
     </td>
     <td class="chgset">
      <a href="<?cs var:item.changeset_href ?>"><?cs var:item.rev ?></a>
     </td>
     <td class="author"><?cs var:log.changes[item.rev].author ?></td>
     <td class="summary"><?cs var:log.changes[item.rev].message ?></td>
    </tr><?cs
   /each ?>
  </tbody>
 </table>

</div>
<?cs include "footer.cs"?>
