<h2>Manage Versions</h2><?cs

if:admin.version.name ?>
 <form class="mod" id="modver" method="post">
  <fieldset>
   <legend>Modify Version:</legend>
   <div class="field">
    <label>Name: <input type="text" name="name"value="<?cs
      var:admin.version.name ?>" /></label>
   </div>
   <div class="field">
    <label>Time: <input type="text" name="time" value="<?cs
      var:admin.version.time ?>"></label>
   </div>
   <div class="field">
    <label>Description: <input type="text" name="description" value="<?cs
      var:admin.version.description ?>"></label>
   </div>
   <div class="buttons">
    <input type="submit" name="cancel" value="Cancel">
    <input type="submit" name="save" value="Save">
   </div>
  </fieldset>
 </form><?cs

else ?>

 <form class="addnew" id="addver" method="post">
  <fieldset>
   <legend>Add Version:</legend>
   <div class="field">
    <label>Name:<input type="text" name="name" id="name"></label>
   </div>
   <div class="field">
    <label>Time: <input type="text" name="time" value="<?cs
      var:admin.version.time ?>"></label>
   </div>
   <div class="buttons">
    <input type="submit" name="add" value="Add">
   </div>
  </fieldset>
 </form>

 <form method="POST">
  <table class="listing" id="verlist">
   <thead>
    <tr><th class="sel">&nbsp;</th><th>Name</th>
    <th>Time</th><th>Default</th></tr>
   </thead><tbody><?cs
   each:ver = admin.versions ?>
   <tr>
    <td><input type="checkbox" name="sel" value="<?cs var:ver.name ?>" /></td>
    <td><a href="<?cs var:ver.href ?>"><?cs var:ver.name ?></a></td>
    <td><?cs var:ver.time ?></td>
     <td class="default"><input type="radio" name="default" value="<?cs
       var:ver.name ?>"<?cs
       if:ver.is_default ?> checked="checked" <?cs /if ?>></td>
   </tr><?cs
   /each ?></tbody>
  </table>
  <div class="buttons">
   <input type="submit" name="remove" value="Remove selected" />
   <input type="submit" name="setdefault" value="Set default version" />
  </div>
 </form><?cs

/if ?>
