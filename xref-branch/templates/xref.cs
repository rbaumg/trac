<?cs set:html.stylesheet = 'css/timeline.css' ?>
<?cs include "header.cs" ?>
<?cs include "macros.cs" ?>

<div id="ctxtnav" class="nav">
 <h2>Xref Navigation</h2>
 <ul><?cs
  if:xref.direction.back ?>
   <li><a href="<?cs var:$trac.current_href ?>?direction=forward"
          title="Show a summary of Trac Objects referenced by <?cs var:base.name ?>">
    Forward Links</a>
   </li><?cs
  else ?>
   <li><a href="<?cs var:$trac.current_href ?>?direction=back"
          title="Show the Trac Objects referencing <?cs var:base.name ?>"
    Backward Links</a>
   </li><?cs
  /if ?>
  <li><a href="<?cs var:$trac.href.orphans ?>"
         title="Show Trac Objects which are not referenced">
    Orphaned Objects</a>
  </li>
 </ul>
 <hr />
</div>
<div id="content" class="wiki">

 <?cs def:anchor(xref) ?>
  <a href="<?cs var:xref.href ?>"><em><?cs var:xref.name ?></em></a><?cs 
 /def ?>

 <?cs set:nlinks = len(xref.links) ?>
 <?cs set:nrelations = len(xref.relations) ?>

 <?cs if:$nlinks + $nrelations == #0 ?>
  <h1>No <?cs var:xref.direction.name ?>s for <?cs call:anchor(xref.base) ?></h1><?cs
 elif: $nlinks + $nrelations == #1 ?>
  <h1>One <?cs var:xref.direction.name ?> for <?cs call:anchor(xref.base) ?></h1><?cs
 else ?>
  <h1><?cs var:xref.count ?> <?cs var:xref.direction.name ?>s for <?cs call:anchor(xref.base) ?></h1><?cs
 /if ?>

 <?cs if:$nrelations > #0 ?>
  <h2>Relationships of <?cs var:xref.base.name ?></h2>
  <dl><?cs
   each:item = xref.relations ?>
    <dt class="<?cs var:item.icon ?>">
     <a href="<?cs var:item.href ?>"><?cs 
      if:xref.direction.back ?>
       <em><?cs var:item.name ?></em>
       <strong><?cs var:item.relation ?></strong>
       <?cs var:xref.base.name ?><?cs
      else ?>
       <?cs var:xref.base.name ?>
       <strong><?cs var:item.relation ?></strong>
       <em><?cs var:item.name ?></em><?cs
      /if ?>
     </a>
    </dt>
    <dd><?cs var:item.context ?></dd><?cs
   /each ?>
  </dl>
 <?cs /if ?>

 <?cs if:$nlinks > #0 ?>
  <?cs if:xref.direction.back ?>
   <h2><?cs var:xref.base.name ?> is referenced in the following Trac Objects:</h2><?cs
  else ?>
   <h2><?cs var:xref.base.name ?> references the following Trac Objects:</h2><?cs
  /if ?>
  <dl><?cs 
   set:previous_name = "" ?><?cs
   each:item = xref.links ?><?cs
    if item.name != previous_name ?><?cs
     set previous_name = item.name ?>
     <dt class="<?cs var:item.icon ?>"><?cs call:anchor(item) ?></dt><?cs
    /if ?>
    <dd><?cs var:item.context ?>   <em>(in the <?cs var:item.facet?>)</em></dd><?cs
   /each ?>
  </dl>
 <?cs /if ?>

</div>

<?cs include "footer.cs" ?>
