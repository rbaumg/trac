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

 <?cs set:n_links = len(xref.links) ?>
 <?cs set:n_in_relations = len(xref.in_relations) ?>
 <?cs set:n_out_relations = len(xref.out_relations) ?>

 <?cs if:$n_links == #0 ?>
  <h1>No Backlinks for <?cs call:anchor(xref.base) ?></h1><?cs
 elif: $n_links == #1 ?>
  <h1>One Backlink for <?cs call:anchor(xref.base) ?></h1><?cs
 else ?>
  <h1><?cs var:xref.count ?> Backlinks for <?cs call:anchor(xref.base) ?></h1><?cs
 /if ?>

 <?cs if:$n_links > #0 ?>
  <h2><?cs 
   call:anchor(xref.base) ?> is referenced <?cs 
   if $n_links == #1 ?>
    in the Wiki of another Trac Object:<?cs
   else ?><?cs
   var:$n_links ?> times in the wiki of other Trac Objects:<?cs
   /if ?>
  </h2>
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

 <?cs if:$n_in_relations > #0 ?>
  <h2><?cs 
   if $n_in_relations == #1 ?> 
    Another Trac Object has a relation<?cs
   else ?>
    Other Trac Objects have <?cs var:$n_in_relations ?> relations<?cs
   /if ?> 
   with <?cs call:anchor(xref.base) ?>:
  </h2>
  <dl><?cs
   each:item = xref.in_relations ?>
    <dt class="<?cs var:item.icon ?>">
     <a href="<?cs var:item.href ?>">
       <em><?cs var:item.name ?></em> <i>&laquo;<?cs var:item.relation ?>&raquo;</i> <?cs var:xref.base.name ?>
     </a>
    </dt>
    <dd><?cs var:item.context ?></dd><?cs
   /each ?>
  </dl>
 <?cs /if ?>

 <?cs if:$n_out_relations > #0 ?>
  <h2><?cs 
   call:anchor(xref.base) ?><?cs 
   if $n_out_relations == #1 ?> 
    has one relation with another Trac Object:<?cs
   else ?>
    has <?cs var:$n_out_relations ?> relations with other Trac Objects:<?cs
   /if ?> 
  </h2>
  <dl><?cs
   each:item = xref.out_relations ?>
    <dt class="<?cs var:item.icon ?>">
     <a href="<?cs var:item.href ?>">
       <?cs var:xref.base.name ?> <i>&laquo;<?cs var:item.relation ?>&raquo;</i> <em><?cs var:item.name ?></em>
     </a>
    </dt>
    <dd><?cs var:item.context ?></dd><?cs
   /each ?>
  </dl>
 <?cs /if ?>

</div>

<?cs include "footer.cs" ?>
