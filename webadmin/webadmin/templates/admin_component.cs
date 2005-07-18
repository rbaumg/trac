<h2>Manage Components</h2><?cs

if admin.component.name ?>
 <form class="mod" id="modcomp" method="post">
  <fieldset>
   <legend>Modify Component:</legend>
   <div class="field">
    <label>Name: <input type="text" name="name" value="<?cs
      var:admin.component.name ?>"></label>
   </div>
   <div class="field">
    <label>Owner: <input type="text" name="owner" value="<?cs
      var:admin.component.owner ?>"></label>
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
    <label>Name: <input type="text" name="name" /></label>
   </div>
   <div class="field">
    <label>Owner:  <input type="text" name="owner" /></label>
   </div>
   <div class="buttons">
    <input type="submit" name="add" value="Add">
   </div>
  </fieldset>
 </form>

 <form method="POST">
  <table class="listing" id="complist">
   <thead>
    <tr><th class="sel">&nbsp;</th><th>Name</th><th>Owner</th></tr>
   </thead><?cs
   each:comp = admin.components ?>
    <tr>
     <td><input type="checkbox" name="sel" value="<?cs var:comp.name ?>" /></td>
     <td><a href="<?cs var:comp.href?>"><?cs var:comp.name ?></a></td>
     <td><?cs var:comp.owner ?></td>
    </tr><?cs
   /each ?>
  </table>
  <div class="buttons">
   <input type="submit" name="remove" value="Remove selected components" />
  </div>
 </form><?cs
 
/if ?>
