<h2><?cs var:admin.enum.heading ?></h2><?cs

if:admin.enum.name ?>
 <form class="mod" id="modenum" method="post">
  <fieldset>
   <legend><?cs var:admin.enum.modify_label ?></legend>
   <div class="field">
    <label>Name: <input type="text" name="name"value="<?cs
      var:admin.enum.name ?>" /></label>
   </div>
   <div class="buttons">
    <input type="submit" name="cancel" value="Cancel">
    <input type="submit" name="save" value="Save">
   </div>
  </fieldset>
 </form><?cs

else ?>

 <form class="addnew" id="addenum" method="post">
  <fieldset>
   <legend><?cs var:admin.enum.add_label ?></legend>
   <div class="field">
    <label>Name:<input type="text" name="name" id="name"></label>
   </div>
   <div class="buttons">
    <input type="submit" name="add" value="Add">
   </div>
  </fieldset>
 </form>

 <form method="POST">
  <table class="listing" id="enumlist">
   <thead>
    <tr><th class="sel">&nbsp;</th><th>Name</th></tr>
   </thead><tbody><?cs
   each:enum = admin.enums ?>
   <tr>
    <td><input type="checkbox" name="sel" value="<?cs var:enum.name ?>" /></td>
    <td><a href="<?cs var:enum.href ?>"><?cs var:enum.name ?></a></td>
   </tr><?cs
   /each ?></tbody>
  </table>
  <div class="buttons">
   <input type="submit" name="remove" value="<?cs var:admin.enum.remove_label ?>" />
  </div>
 </form><?cs

/if ?>
