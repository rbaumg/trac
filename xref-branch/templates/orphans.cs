<?cs set:html.stylesheet = 'css/timeline.css' ?>
<?cs include "header.cs" ?>
<?cs include "macros.cs" ?>

<div id="ctxtnav" class="nav">
 <h2>Xref Navigation</h2>
 <ul>
 </ul>
 <hr />
</div>
<div id="content" class="wiki">

 <?cs def:anchor(xref) ?>
 <a href="<?cs var:xref.href ?>"><em><?cs var:xref.name ?></em></a><?cs 
 /def ?>

 <h1><?cs var:len(orphans) ?> Orphaned Trac Objects</h1>
  <p>The following objects are not referenced by any other objects</p>
  <dl><?cs 
   set:previous_type = "" ?><?cs
   each:item = orphans ?><?cs
    if:item.type != previous_type ?><?cs
     set:previous_type = item.type ?>
     <h2>Orphaned <?cs var:item.type ?> objects:</h2><?cs
    /if ?>
    <dt class="<?cs var:item.icon ?>"><?cs call:anchor(item) ?></dt><?cs
   /each ?>
 </dl>

</div>

<?cs include "footer.cs" ?>
