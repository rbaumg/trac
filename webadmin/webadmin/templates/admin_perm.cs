<h2>Manage Permissions</h2>

<form method="post">
  <table class="listing" id="verlist">
   <thead>
    <tr><th class="checkboxcol">&nbsp;</th><th>Subject</th><th>Action</th></tr>
   </thead><?cs
   each:perm = admin.perms ?>
   <tr>
    <td><input type="checkbox" name="sel" value="<?cs var:perm.key ?>" /></td>
    <td><?cs var:perm.subject ?></td>
    <td><?cs var:perm.action ?></td>
   </tr><?cs
   /each ?>
  </table>
  <input type="submit" name="remove" value="Remove Selected">
</form>

<form class="float-left align-right" method="post">
  <fieldset>
   <legend>Add Permission:</legend>
   <label for="subject">Subject:</label>
   <input type="text" name="subject" id="subject">
   <label for="action">Action:</label>
   <?cs call:hdf_select(admin.actions, "action", "", 0) ?>
   <br />
   <input type="submit" name="add" value=" Add ">
  </fieldset>
</form>
