<h2>Manage Versions</h2>

<?cs if admin.version.name ?>

<form class="float-left" method="post">
  <fieldset class="align-right">
   <legend>Modify Version:</legend>
   <label for="name">Name:</label>
   <input type="text" name="name" id="name" 
          value="<?cs var:admin.version.name ?>">
   <br />
   <label for="time">Time:</label>
   <input type="text" name="time" id="time" 
          value="<?cs var:admin.version.time ?>">
   <br />
   <label for="time">Description:</label>
   <input type="text" name="description" id="description" 
          value="<?cs var:admin.version.description ?>">
   <br />
   <input type="submit" name="cancel" value="Cancel">
   <input type="submit" name="remove" value="Remove">
   <input type="submit" name="save" value="Save">
  </fieldset>
</form>

<?cs else ?>

  <table class="listing" id="verlist">
   <thead>
    <tr><th>Name</th><th>Description</th><th>Time</th></tr>
   </thead><?cs
   each:ver = admin.versions ?>
   <tr>
    <td><a href="<?cs var:ver.href ?>"><?cs var:ver.name ?></a></td>
    <td><?cs var:ver.description ?></td>
    <td><?cs var:ver.time ?></td>
   </tr><?cs
   /each ?>
  </table>
  <br />
  <form class="float-left align-right" method="post">
   <fieldset>
    <legend>Add Version:</legend>
    <label for="name">Name:</label><input type="text" name="name" id="name">
    <br />
    <input type="submit" name="add" value=" Add ">
   </fieldset>
  </form>

<?cs /if ?>
