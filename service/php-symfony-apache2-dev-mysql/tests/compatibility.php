<?php

require dirname(__DIR__) . '/vendor/autoload.php';

use App\Controller\GetLists\ListResponse;
use App\Entity\Account;
use App\Entity\ListEntity;
use App\Entity\Task;
use Doctrine\DBAL\Platforms\MySQLPlatform;
use Doctrine\DBAL\Types\Type;
use Doctrine\ORM\Mapping\Column;

foreach ([Account::class, ListEntity::class, Task::class] as $entity) {
    $property = new ReflectionProperty($entity, 'creation_date');
    $mapping = $property->getAttributes(Column::class)[0]->getArguments();
    $value = Type::getType($mapping['type'])->convertToPHPValue(
        '2026-10-29 12:03:32.000000',
        new MySQLPlatform()
    );
    if ($value->format('Y-m-d H:i:s.u') !== '2026-10-29 12:03:32.000000') {
        throw new RuntimeException('Timestamp conversion failed for ' . $entity);
    }
}

if ((new ListResponse())->tasks !== []) {
    throw new RuntimeException('Empty lists must serialize tasks as an array');
}

echo "PASS timestamp mappings and empty task arrays\n";
