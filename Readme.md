# BackMeUp

BackupMeUp is a dockerized Backup Tool which does encrypted backups into your Google Drive.

## Example usage when all requirements are fulfilled

Using one volume for data to back up:
```
docker run --rm -v /home/myImportantFiles:/backMeUp/myImportantFiles \
-v ${PWD}/mandatoryVolume:/mandatoryVolume \
-e GPG_KEY_ID=9C81C743343A836D0241738BE2F76FE5E7E61B2A \
--name backmeup \
hackerh/backmeup \
upload /backMeUp
```

Using three volumes for data to back up:

```
docker run --rm -v /home/myImportantFiles:/backMeUp/myImportantFiles \
-v /home/mySecondImportantFiles:/backMeUp/mySecondImportantFiles \
-v /home/myThirdImportantFiles:/backMeUp/myThirdImportantFiles \
-v ${PWD}/mandatoryVolume:/mandatoryVolume \
-e GPG_KEY_ID=9C81C743343A836D0241738BE2F76FE5E7E61B2A \
--name backmeup \
hackerh/backmeup \
upload /backMeUp
```

Download a backup:
```
docker run --rm -v /home/myImportantFiles:/backMeUp/myImportantFiles \
-v ${PWD}/mandatoryVolume:/mandatoryVolume \
-v ${PWD}/backups:/destinationFolder
-e GPG_KEY_ID=9C81C743343A836D0241738BE2F76FE5E7E61B2A \
--name backmeup \
hackerh/backmeup \
download myBackup.zip.gpg /destinationFolder
```

## Prerequisites
Further explanations can be found below
To be able to use backmeup properly you need:
- Docker
- a GPG key and its public and private key each as a file
- a Google account and a Google cloud key with activated Google Drive API for your account
- a credentials.json file
- a token.pickle file (backmeup will generate it for you)

## How it works
You can pass an arbitrary amount of volumes into the docker container.
All files and subdirectories in this directory will then be zipped and afterwards encrypted with a GPG key.
You provide the GPG key as a file in the project's `mandatoryVolume` and the gpg key id as the environment variable `GPG_KEY_ID` when starting the container.
The encrypted file will then be uploaded to your GoogleDrive with a Google Cloud Key;
on the first upload attempt Google Drive will require you to grant backMeUp access
which will also create and save a self extending token in `mandatoryVolume/credentials.json`.

## How to create a GPG key
In the following we will use the terminal to create a GPG key only designated for encrypting data.
This is not the way GPG is supposed to be used however it is expedient for this project.

Make sure to use gpg 2.1.18 or later as those use meaningful default settings.
```
$ gpg --version
gpg (GnuPG) 2.2.16-unknown
```

`gpg --expert --full-gen-key`

```
Please select what kind of key you want:
(1) RSA and RSA (default)
(2) DSA and Elgamal
(3) DSA (sign only)
(4) RSA (sign only)
(7) DSA (set your own capabilities)
(8) RSA (set your own capabilities)
(9) ECC and ECC
(10) ECC (sign only)
(11) ECC (set your own capabilities)
(13) Existing key
Your selection? 8
```

```
Possible actions for a RSA key: Sign Certify Encrypt Authenticate
Current allowed actions: Sign Certify Encrypt

(S) Toggle the sign capability
(E) Toggle the encrypt capability
(A) Toggle the authenticate capability
(Q) Finished

Your selection? s
```

```
Possible actions for a RSA key: Sign Certify Encrypt Authenticate
Current allowed actions: Certify Encrypt

(S) Toggle the sign capability
(E) Toggle the encrypt capability
(A) Toggle the authenticate capability
(Q) Finished

Your selection? q
```

```
RSA keys may be between 1024 and 4096 bits long.
What keysize do you want? (2048) 4096
```

```
Please specify how long the key should be valid.
         0 = key does not expire
      <n>  = key expires in n days
      <n>w = key expires in n weeks
      <n>m = key expires in n months
      <n>y = key expires in n years
Key is valid for? (0) 2y
```

```
Key expires at Mi, 11. Aug 2021 01:12:16
Is this correct? (y/N) y
```

```
GnuPG needs to construct a user ID to identify your key.

Real name: myBackupUser
```

```
Email address:
```

```
Comment:
```

```
You selected this USER-ID:
    "myBackupUser"

Change (N)ame, (C)omment, (E)mail or (O)kay/(Q)uit? o
```

Do NOT type a password if you are prompted, just click ok and finish the creation without setting a passphrase.
Note: In older GPG versions it might not be possible to create keys without passphrase, this guide was tested with gpg 2.2.16.

## Find out the GPG key id
`gpg -k myBackupUser`
```
pub   rsa4096 2019-08-11 [CE] [expires: 2021-08-10]
      9C81C743343A836D0241738BE2F76FE5E7E61B2A
uid           [ultimate] myBackupUser
```
In this case `9C81C743343A836D0241738BE2F76FE5E7E61B2A` is the GPG key id.

## How to export the GPG key as a file
Note that you have to replace `YOUR_GPG_KEY_ID` with your actual GPG key id.
public key:
`gpg --export --armor YOUR_GPG_KEY_ID > key.pub.asc`
private key:
`gpg --export-secret-keys --armor YOUR_GPG_KEY_ID > key.sec.asc`
Put both files into the `mandatoryVolume`.

## How to create a Google Cloud Key
Follow "Step 1" described in [the developer docs.](https://developers.google.com/drive/api/v3/quickstart/python) and save the `credentials.json` in the `mandatoryVolume`.

## How to manually decrypt my backup after I downloaded it from Google Drive?
Note that you need the private Key available on your system corresponding to the public key you used for encryption.
If you are using a different system than the one you created the gpg keypair on, you have to export the keys on the initial system and import them on your system.
`gpg --output myBackup.zip --decrypt myBackup.zip.gpg`

## Possible enhancements
 - set a custom backup filename as environment variable
 - set a subdirectory for googledrive destination as environment variable
 - extract gpg key id from keyfile:
 https://stackoverflow.com/questions/39596446/how-to-get-gpg-public-key-in-bash
 - support gpg keys with passphrase
 - extract python script from volume
 - more backup revision download capabilities
      - show all versions of a backup
      - choose backup X
      - choose latest backup from date
      - choose latest backup from date at hour
 - backmeup as pypi package

## Do you have questions or suggestions?
Feel free to create an issue.
