<h2>Manage Components</h2><?cs

if admin.component.name ?>
 <form class="mod" id="modcomp" method="post">
  <fieldset>
   <legend>Modify Component:</legend>
   <div class="field">
    <label>Name:<input type="text" name="name" value="<?cs
      var:admin.component.name ?>"></label>
   </div>
   <div class="field">
    <label>Owner:<?cs
     if:len(admin.owners) ?><?cs
      call:hdf_select(admin.owners, "owner", "", 0) ?><?cs
     else ?><input type="text" name="owner" value="<?cs
      var:admin.component.owner ?>" /><?cs
     /if ?></label>
   </div>
   <div class="buttons">
    <input type="submit" name="cancel" value="Cancel" />
    <input type="submit" name="save" value="Save" />
   </div>
  </fieldset>
 </form><?cs

else ?>
 <form class="addnew" id="addcomp" method="post">
  <fieldset>
   <legend>Add Component:</legend>
   <div class="field">
    <label>Name:<br /><input type="text" name="name" /></label>
   </div>
   <div class="field">
    <label>Owner:<br /><?cs
     if:len(admin.owners) ?><?cs
      call:hdf_select(admin.owners, "owner", "", 0) ?><?cs
     else ?><input type="text" name="owner" /><?cs
     /if ?></label>
   </div>
   <div class="buttons">
    <input type="submit" name="add" value="Add">
   </div>
  </fieldset>
 </form>

 <form method="POST">
  <table class="listing" id="complist">
   <thead>
    <tr><th class="sel">&nbsp;</th><th>Name</th>
    <th>Owner</th><th>Default</th></tr>
   </thead><?cs
   each:comp = admin.components ?>
    <tr>
     <td class="sel"><input type="checkbox" name="sel" value="<?cs
       var:comp.name ?>" /></td>
     <td class="name"><a href="<?cs var:comp.href?>"><?cs
       var:comp.name ?></a></td>
     <td class="owner"><?cs var:comp.owner ?></td>
     <td class="default"><input type="radio" name="default" value="<?cs
       var:comp.name ?>"<?cs
       if:comp.is_default ?> checked="checked" <?cs /if ?>></td>
    </tr><?cs
   /each ?>
  </table>
  <div class="buttons">
   <input type="submit" name="remove" value="Remove selected" />
   <input type="submit" name="setdefault" value="Set default component" />
  </div>
 </form><?cs

/if ?>
