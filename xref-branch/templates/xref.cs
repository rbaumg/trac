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

 <h1>Cross-references for <?cs call:anchor(xref.base) ?></h1>

 <h2 id='backlinks'>Implicit references (<?cs var:$n_links ?>)</h2>
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

 <h2 id='incoming-relations'>Incoming relations (<?cs var:$n_in_relations ?>)</h2>
 <dl><?cs
  each:item = xref.in_relations ?>
   <dt class="<?cs var:item.icon ?>">
    <a href="<?cs var:item.href ?>">
      <em><?cs var:item.name ?></em> <?cs call:relation(item.relation) ?> <?cs var:xref.base.name ?>
    </a>
   </dt>
   <dd><?cs var:item.context ?></dd><?cs
  /each ?>
 </dl>

 <h2 id='outgoing-relations'>Outgoing relations (<?cs var:$n_out_relations ?>)</h2>
 <dl><?cs
  each:item = xref.out_relations ?>
   <dt class="<?cs var:item.icon ?>">
    <a href="<?cs var:item.href ?>">
      <?cs var:xref.base.name ?> <?cs call:relation(item.relation) ?> <em><?cs var:item.name ?></em>
    </a>
   </dt>
   <dd><?cs var:item.context ?></dd><?cs
  /each ?>
 </dl>

</div>

<?cs include "footer.cs" ?>
